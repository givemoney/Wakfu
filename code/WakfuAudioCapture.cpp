#include <windows.h>
#include <audioclient.h>
#include <mmdeviceapi.h>
#include <audioclientactivationparams.h>
#include <wrl.h>
#include <atomic>
#include <thread>
#include <cstdio>
#include <vector>
#include <string>
#include <share.h>
#include <mutex>
#include <cmath>
using namespace Microsoft::WRL;
static long long Clock(){LARGE_INTEGER t,f;QueryPerformanceCounter(&t);QueryPerformanceFrequency(&f);return (long long)((long double)t.QuadPart*10000000/f.QuadPart);}
class Activation:public RuntimeClass<RuntimeClassFlags<ClassicCom>,FtmBase,IActivateAudioInterfaceCompletionHandler>{
public:
 HANDLE done=CreateEventW(nullptr,FALSE,FALSE,nullptr);HRESULT result=E_PENDING;ComPtr<IAudioClient> client;
 ~Activation(){CloseHandle(done);}
 STDMETHOD(ActivateCompleted)(IActivateAudioInterfaceAsyncOperation* op){ComPtr<IUnknown> u;HRESULT activate;result=op->GetActivateResult(&activate,&u);if(SUCCEEDED(result))result=activate;if(SUCCEEDED(result))result=u.As(&client);SetEvent(done);return S_OK;}
};
struct Recording{
 std::atomic<bool> stop{false};std::thread worker;HANDLE ready=CreateEventW(nullptr,FALSE,FALSE,nullptr);
 std::atomic<HRESULT> result{E_PENDING};DWORD pid;std::wstring path;long long epoch;FILE* file=nullptr;unsigned long long frames=0;ComPtr<IAudioClient> client;ComPtr<IAudioCaptureClient> capture;
 bool live=false;std::mutex ringLock;std::vector<short> ring=std::vector<short>(44100*2*4);size_t head=0,count=0;
 Recording(DWORD p,const wchar_t* s,long long e):pid(p),path(s),epoch(e){}
 ~Recording(){CloseHandle(ready);}
 void write(const short* data,size_t n){
  if(live){
   std::lock_guard<std::mutex> lock(ringLock);size_t len=n*2,cap=ring.size();
   if(len>cap){data+=len-cap;len=cap;}
   if(count+len>cap){size_t drop=count+len-cap;head=(head+drop)%cap;count-=drop;}
   size_t end=(head+count)%cap,first=(len<cap-end?len:cap-end);memcpy(&ring[end],data,first*2);if(len>first)memcpy(ring.data(),data+first,(len-first)*2);count+=len;frames+=n;
  }else if(fwrite(data,4,n,file)!=n){result=HRESULT_FROM_WIN32(ERROR_WRITE_FAULT);stop=true;}else frames+=n;
 }
 void zeros(unsigned long long n){short data[8192]={};while(n&&!stop){size_t k=(size_t)(n>4096?4096:n);write(data,k);n-=k;}}
 void run(){
  HRESULT init=CoInitializeEx(nullptr,COINIT_MULTITHREADED);result=init;
  if(FAILED(init)){SetEvent(ready);return;}
  auto cb=Make<Activation>();AUDIOCLIENT_ACTIVATION_PARAMS params={};params.ActivationType=AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK;params.ProcessLoopbackParams.TargetProcessId=pid;params.ProcessLoopbackParams.ProcessLoopbackMode=PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE;
  PROPVARIANT pv={};pv.vt=VT_BLOB;pv.blob.cbSize=sizeof(params);pv.blob.pBlobData=(BYTE*)&params;ComPtr<IActivateAudioInterfaceAsyncOperation> op;
  result=ActivateAudioInterfaceAsync(VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK,__uuidof(IAudioClient),&pv,cb.Get(),&op);
  if(SUCCEEDED(result)){if(WaitForSingleObject(cb->done,10000)!=WAIT_OBJECT_0)result=HRESULT_FROM_WIN32(WAIT_TIMEOUT);else result=cb->result;}
  HANDLE samples=CreateEventW(nullptr,FALSE,FALSE,nullptr);
  WAVEFORMATEX fmt={WAVE_FORMAT_PCM,2,44100,176400,4,16,0};
  if(SUCCEEDED(result)){client=cb->client;result=client->Initialize(AUDCLNT_SHAREMODE_SHARED,AUDCLNT_STREAMFLAGS_LOOPBACK|AUDCLNT_STREAMFLAGS_EVENTCALLBACK|AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM,0,0,&fmt,nullptr);}
  if(SUCCEEDED(result))result=client->SetEventHandle(samples);
  if(SUCCEEDED(result))result=client->GetService(IID_PPV_ARGS(&capture));
  if(SUCCEEDED(result)&&!live){file=_wfsopen(path.c_str(),L"wb",_SH_DENYNO);if(!file)result=HRESULT_FROM_WIN32(ERROR_ACCESS_DENIED);}
  if(SUCCEEDED(result)){
   if(file){fwrite("RIFF",1,4,file);DWORD empty=0;fwrite(&empty,4,1,file);fwrite("WAVEfmt ",1,8,file);DWORD fmtSize=16;fwrite(&fmtSize,4,1,file);fwrite(&fmt,1,16,file);fwrite("data",1,4,file);fwrite(&empty,4,1,file);fflush(file);}
   result=client->Start();
  }
  SetEvent(ready);
  if(SUCCEEDED(result))while(!stop){
   WaitForSingleObject(samples,30);UINT32 available=0;result=capture->GetNextPacketSize(&available);if(FAILED(result))break;
   while(available&&!stop){
    BYTE* data=nullptr;UINT32 n=0;DWORD flags=0;UINT64 pos=0,qpc=0;result=capture->GetBuffer(&data,&n,&flags,&pos,&qpc);if(FAILED(result))break;
    // QPC timestamps align all files to the same Windows audio timeline.
    if(!(flags&AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR)&&qpc>(UINT64)epoch){auto target=(unsigned long long)((qpc-epoch)*44100/10000000);if(target>frames)zeros(target-frames);}
    if(flags&AUDCLNT_BUFFERFLAGS_SILENT)zeros(n);else write((short*)data,n);
    capture->ReleaseBuffer(n);if(FAILED(result))break;result=capture->GetNextPacketSize(&available);if(FAILED(result))break;
   }
   if(file&&fflush(file)!=0){result=HRESULT_FROM_WIN32(ERROR_WRITE_FAULT);break;}
   if(FAILED(result))break;
  }
  if(client)client->Stop();
  if(file){DWORD bytes=(DWORD)(frames*4),size=bytes+36;fseek(file,4,SEEK_SET);fwrite(&size,4,1,file);fseek(file,40,SEEK_SET);fwrite(&bytes,4,1,file);fclose(file);file=nullptr;}
  capture.Reset();client.Reset();op.Reset();cb.Reset();CloseHandle(samples);CoUninitialize();
 }
};
extern "C" __declspec(dllexport) long long AudioClock(){return Clock();}
extern "C" __declspec(dllexport) void* StartRecording(DWORD pid,const wchar_t* path,long long epoch,int* error){
 auto r=new Recording(pid,path,epoch);r->worker=std::thread([r]{r->run();});WaitForSingleObject(r->ready,INFINITE);*error=r->result;if(FAILED(r->result)){r->stop=true;r->worker.join();delete r;return nullptr;}return r;
}
extern "C" __declspec(dllexport) int StopRecording(void* ptr){auto r=(Recording*)ptr;r->stop=true;r->worker.join();int hr=r->result;delete r;return hr;}
extern "C" __declspec(dllexport) void* StartLiveCapture(DWORD pid,long long epoch,int* error){
 auto r=new Recording(pid,L"",epoch);r->live=true;r->worker=std::thread([r]{r->run();});WaitForSingleObject(r->ready,INFINITE);*error=r->result;if(FAILED(r->result)){r->stop=true;r->worker.join();delete r;return nullptr;}return r;
}
extern "C" __declspec(dllexport) int ReadLiveCapture(void* ptr,short* data,int capacity){
 auto r=(Recording*)ptr;HRESULT hr=r->result;if(FAILED(hr))return hr;
 std::lock_guard<std::mutex> lock(r->ringLock);size_t len=r->count<(size_t)capacity?r->count:(size_t)capacity;len-=len%16;
 size_t first=len<r->ring.size()-r->head?len:r->ring.size()-r->head;memcpy(data,&r->ring[r->head],first*2);if(len>first)memcpy(data+first,r->ring.data(),(len-first)*2);r->head=(r->head+len)%r->ring.size();r->count-=len;return (int)len;
}
extern "C" __declspec(dllexport) int TestTone(){
 WAVEFORMATEX fmt={WAVE_FORMAT_PCM,2,44100,176400,4,16,0};HWAVEOUT out;MMRESULT hr=waveOutOpen(&out,WAVE_MAPPER,&fmt,0,0,CALLBACK_NULL);if(hr)return hr;
 std::vector<short> sound(44100);for(int i=0;i<22050;i++)sound[2*i]=sound[2*i+1]=(short)(700*sin(i*2*3.141592653589793*880/44100));
 WAVEHDR header={};header.lpData=(LPSTR)sound.data();header.dwBufferLength=(DWORD)(sound.size()*2);waveOutPrepareHeader(out,&header,sizeof(header));waveOutWrite(out,&header,sizeof(header));while(!(header.dwFlags&WHDR_DONE))Sleep(10);waveOutUnprepareHeader(out,&header,sizeof(header));waveOutClose(out);return 0;
}

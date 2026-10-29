using System;
using System.Drawing;
using System.Windows.Forms;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Diagnostics;
using System.IO;
using System.Collections.Generic;
using System.Web.Script.Serialization;

class WakfuPanel : Form {
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern IntPtr FindWindow(string cls,string title);
 [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
 [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h,int n);
 [DllImport("user32.dll")] static extern short GetAsyncKeyState(int key);
 [StructLayout(LayoutKind.Sequential)] struct KI {public ushort vk,scan;public uint flags,time;public UIntPtr extra;}
 [StructLayout(LayoutKind.Sequential)] struct MI {public int x,y;public uint data,flags,time;public UIntPtr extra;}
 [StructLayout(LayoutKind.Explicit)] struct Union {[FieldOffset(0)]public KI k;[FieldOffset(0)]public MI m;}
 [StructLayout(LayoutKind.Sequential)] struct Input {public uint type;public Union data;}
 [DllImport("user32.dll",SetLastError=true)] static extern uint SendInput(uint n,Input[] inputs,int size);
 readonly string[] names={"Abouk Imak - WAKFU","Roubouze Yabess - WAKFU","Naheulbeuuk - WAKFU"};
 const string FollowCommand="/follow \"Hadak Lkelb\"";
 readonly Button space=new Button(),escape=new Button(),follow=new Button(),one=new Button(),eight=new Button();
 readonly Button[] swapButtons={new Button(),new Button(),new Button()};
 readonly Button returnP=new Button();
 readonly Button windowsToggle=new Button();
 readonly Panel swapSection=new Panel();
 readonly string[] swapNames={"Roubouze Yabess","Abouk Imak","Naheulbeuuk"};
 readonly string swapSession=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"app","manual-commandes",Guid.NewGuid().ToString("N"));
 readonly Label status=new Label();
 bool busy,closing,swapped,windowsExpanded;
 int activeSwapIndex=-1;
 WakfuPanel(){
  Text="Wakfu — commandes (version 15)";ClientSize=new Size(430,338);TopMost=true;StartPosition=FormStartPosition.CenterScreen;
  AddButton(space,"Espace",15,15);AddButton(escape,"Échap",225,15);AddButton(follow,"Suivre Hadak Lkelb",15,90);AddButton(one,"1",225,90,95);AddButton(eight,"8",330,90,95);
  windowsToggle.SetBounds(15,165,400,30);windowsToggle.Font=new Font("Segoe UI",10);windowsToggle.TextAlign=ContentAlignment.MiddleLeft;windowsToggle.Padding=new Padding(4,0,0,0);Controls.Add(windowsToggle);
  windowsToggle.Click+=(s,e)=>{windowsExpanded=!windowsExpanded;UpdateSwapSection();};
  swapSection.SetBounds(15,203,400,55);Controls.Add(swapSection);
  for(int i=0;i<swapButtons.Length;i++){
   int index=i;Button b=swapButtons[i];b.Text=swapNames[i];b.SetBounds(i*136,0,128,55);b.Font=new Font("Segoe UI",9.5f);swapSection.Controls.Add(b);
   b.Click+=async(s,e)=>await SendSwap(index);
  }
  returnP.Text="Retour à P";returnP.SetBounds(0,0,400,55);returnP.Font=new Font("Segoe UI",13);returnP.Visible=false;swapSection.Controls.Add(returnP);
  returnP.Click+=async(s,e)=>await SendSwap(-1);
  status.SetBounds(15,203,400,120);status.Font=new Font("Segoe UI",10);Controls.Add(status);UpdateSwapSection();
  space.Click+=async(s,e)=>await SendBatch(0);
  escape.Click+=async(s,e)=>await SendBatch(1);
  follow.Click+=async(s,e)=>await SendBatch(2);
  eight.Click+=async(s,e)=>await SendBatch(3);
  one.Click+=async(s,e)=>await SendBatch(4);
  FormClosing+=async(s,e)=>{
   if(closing)return;
   if(busy){e.Cancel=true;status.Text="Attends la fin de la commande avant de fermer.";return;}
   if(swapped){e.Cancel=true;await SendSwap(-1);if(!swapped){closing=true;Close();}}
   else closing=true;
  };
  Shown+=(s,e)=>Detect();
 }
 void AddButton(Button b,string text,int x,int y,int width=200){b.Text=text;b.SetBounds(x,y,width,65);b.Font=new Font("Segoe UI",text.Length>10?12:17);Controls.Add(b);}
 void Detect(){status.Text="";foreach(string name in names)status.Text+=name+": "+(FindWindow(null,name)==IntPtr.Zero?"introuvable":"détectée")+Environment.NewLine;}
 void EnableButtons(bool value){space.Enabled=value;escape.Enabled=value;follow.Enabled=value;one.Enabled=value;eight.Enabled=value;foreach(Button b in swapButtons)b.Enabled=value&&!swapped;returnP.Enabled=value;}
 void UpdateSwapSection(){
  SuspendLayout();
  string current=swapped?(activeSwapIndex>=0?swapNames[activeSwapIndex]+" sur le principal":"Échange actif"):"";
  windowsToggle.Text="Fenêtres"+(current.Length>0?" · "+current:"")+" "+(windowsExpanded?"▾":"▸");
  windowsToggle.AccessibleName="Fenêtres";windowsToggle.AccessibleDescription=windowsExpanded?"Replier les options de fenêtres":"Afficher les options de fenêtres";
  foreach(Button b in swapButtons)b.Visible=!swapped;
  returnP.Visible=swapped;if(swapped)returnP.BringToFront();
  swapSection.Visible=windowsExpanded;
  status.Top=windowsExpanded?268:203;
  ClientSize=new Size(ClientSize.Width,windowsExpanded?403:338);
  ResumeLayout();
 }
 void ShowSwapState(bool active){swapped=active;if(!active)activeSwapIndex=-1;UpdateSwapSection();}
 async Task SendSwap(int index){
  if(busy||closing||(index>=0&&swapped))return;
  busy=true;EnableButtons(false);
  if(index>=0)activeSwapIndex=index;
  try{
   Directory.CreateDirectory(swapSession);string resultPath=Path.Combine(swapSession,"resultat.json");
   if(File.Exists(resultPath))File.Delete(resultPath);
   string script=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"app","CommandesSwap.py");
   string action=index<0?"return":"swap";
   ProcessStartInfo start=new ProcessStartInfo(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"runtime","python.exe"),"\""+script+"\" "+action+" \""+swapSession+"\""+(index<0?"":" "+index));
   start.UseShellExecute=false;start.CreateNoWindow=true;start.WindowStyle=ProcessWindowStyle.Hidden;
   start.WorkingDirectory=AppDomain.CurrentDomain.BaseDirectory;
   using(Process process=Process.Start(start)){await Task.Run(()=>process.WaitForExit());}
   if(!File.Exists(resultPath))throw new Exception("Le déplacement n’a pas pu démarrer. Tes fenêtres sont conservées.");
   var result=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(resultPath));
   ShowSwapState(Convert.ToBoolean(result["active"]));status.Text=Convert.ToString(result["message"]);
   if(result.ContainsKey("focused")&&!Convert.ToBoolean(result["focused"]))status.Text+="\r\nClique sur la fenêtre choisie pour lui donner le focus.";
  }catch(Exception ex){
   string statePath=Path.Combine(swapSession,"etat.json");
   if(File.Exists(statePath)){try{var state=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(statePath));ShowSwapState(Convert.ToBoolean(state["active"]));}catch{}}
   status.Text="Déplacement interrompu : "+ex.Message;
  }
  finally{if(!closing)EnableButtons(true);busy=false;}
 }
 static Input MakeInput(ushort vk,ushort scan,uint flags){Input i=new Input();i.type=1;i.data.k.vk=vk;i.data.k.scan=scan;i.data.k.flags=flags;return i;}
 static void Tap(ushort vk,ushort scan){
  Input[] inputs={MakeInput(vk,scan,0),MakeInput(vk,scan,2)};
  uint sent=SendInput(2,inputs,Marshal.SizeOf(typeof(Input)));
  if(sent!=2){SendInput(1,new Input[]{MakeInput(vk,scan,2)},Marshal.SizeOf(typeof(Input)));throw new Exception("Envoi de touche bloqué.");}
 }
 static void TapPhysical(ushort scan){
  Input[] inputs={MakeInput(0,scan,8),MakeInput(0,scan,10)};
  if(SendInput(2,inputs,Marshal.SizeOf(typeof(Input)))!=2){SendInput(1,new Input[]{MakeInput(0,scan,10)},Marshal.SizeOf(typeof(Input)));throw new Exception("Envoi de touche bloqué.");}
 }
 void RequireFocus(IntPtr h){if(closing||GetForegroundWindow()!=h)throw new Exception("Envoi interrompu : la fenêtre active a changé.");}
 async Task ActivateWindow(IntPtr h){
  bool restored=IsIconic(h);
  if(restored)ShowWindow(h,9);
  SetForegroundWindow(h);
  // Wait for actual focus, then allow the game to process the activation.
  for(int elapsed=0;GetForegroundWindow()!=h;elapsed+=15){
   if(closing||elapsed>=450)throw new Exception("Envoi interrompu : impossible d'activer la fenêtre.");
   await Task.Delay(15);
  }
  await Task.Delay(restored?120:60);RequireFocus(h);
 }
 async Task TypeCommand(IntPtr h){
  foreach(char c in FollowCommand){
   RequireFocus(h);
   Input[] inputs={MakeInput(0,c,4),MakeInput(0,c,6)};
   if(SendInput(2,inputs,Marshal.SizeOf(typeof(Input)))!=2)throw new Exception("Saisie du texte bloquée ; commande non validée.");
   await Task.Delay(5);
  }
 }
 public static List<string> DetectedTargets(IEnumerable<string> candidates,Func<string,bool> exists){
  var targets=new List<string>();foreach(string name in candidates)if(exists(name))targets.Add(name);return targets;
 }
 async Task SendBatch(int action){
  bool isEscape=action==1,isFollow=action==2;
  if(busy||closing)return;
  foreach(int key in new int[]{16,17,18,91,92})if((GetAsyncKeyState(key)&0x8000)!=0){status.Text="Relâchez Maj, Ctrl, Alt et Windows avant de cliquer.";return;}
  var targets=DetectedTargets(names,name=>FindWindow(null,name)!=IntPtr.Zero);
  if(targets.Count==0){status.Text="Aucune session cible WAKFU détectée. Ouvrez au moins une des sessions indiquées.";return;}
  busy=true;EnableButtons(false);string result="";
  try{
   foreach(string name in targets){
    if(closing)break;
    IntPtr h=FindWindow(null,name);
    if(h==IntPtr.Zero){result+=name+": introuvable\r\n";continue;}
    await ActivateWindow(h);
    if(isFollow){
     Tap(0x0D,0x1C);await Task.Delay(120);RequireFocus(h);
     await TypeCommand(h);await Task.Delay(50);RequireFocus(h);Tap(0x0D,0x1C);
     await Task.Delay(120);RequireFocus(h);Tap(0x1B,0x01);
     result+=name+": commande /follow et Échap envoyés\r\n";
    }else if(action==3||action==4){TapPhysical((ushort)(action==4?0x02:0x09));result+=name+": touche "+(action==4?"1":"8")+" envoyée\r\n";}else{Tap((ushort)(isEscape?0x1B:0x20),(ushort)(isEscape?0x01:0x39));result+=name+(isEscape?": Échap envoyé\r\n":": Espace envoyé\r\n");}
    await Task.Delay(40);
   }
  }catch(Exception ex){result+=ex.Message;}
  finally{busy=false;if(!closing){status.Text=result;EnableButtons(true);SetForegroundWindow(Handle);}}
 }
 [STAThread] static void Main(){
  bool first;
  using(var mutex=new System.Threading.Mutex(true,"Local\\WakfuBoardCommandes",out first)){
   if(!first){IntPtr existing=FindWindow(null,"Wakfu — commandes (version 15)");if(existing!=IntPtr.Zero){ShowWindow(existing,9);SetForegroundWindow(existing);}return;}
   Application.EnableVisualStyles();Application.Run(new WakfuPanel());
  }
 }
}



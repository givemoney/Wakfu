using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;

class LancerSiteWakfu {
 [STAThread] static void Main(){
  bool first;
  using(Mutex gate=new Mutex(true,"Local\\WakfuBoardSiteLauncher",out first)){
   if(!first)return;
   try {
    string site=@"E:\IA\Wakfu",script=Path.Combine(site,"launch.py");
    if(!File.Exists(script))throw new FileNotFoundException("Le dossier du site est introuvable : "+site);
    string logs=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"app","site-wakfu");Directory.CreateDirectory(logs);
    var output=new StringBuilder();var errors=new StringBuilder();object sync=new object();
    var start=new ProcessStartInfo(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"runtime","python.exe"),"-X utf8 -B \""+script+"\"");
    start.WorkingDirectory=site;start.UseShellExecute=false;start.CreateNoWindow=true;start.WindowStyle=ProcessWindowStyle.Hidden;
    start.RedirectStandardOutput=true;start.RedirectStandardError=true;start.StandardOutputEncoding=Encoding.UTF8;start.StandardErrorEncoding=Encoding.UTF8;
    using(var process=new Process{StartInfo=start}){
     process.OutputDataReceived+=(s,e)=>{if(e.Data!=null)lock(sync)output.AppendLine(e.Data);};
     process.ErrorDataReceived+=(s,e)=>{if(e.Data!=null)lock(sync)errors.AppendLine(e.Data);};
     process.Start();process.BeginOutputReadLine();process.BeginErrorReadLine();process.WaitForExit();
     File.WriteAllText(Path.Combine(logs,"dernier-lancement.log"),DateTime.Now.ToString("s")+Environment.NewLine+output+errors,Encoding.UTF8);
     if(process.ExitCode!=0)throw new Exception(errors.Length>0?errors.ToString().Trim():"Le serveur ne démarre pas. Vérifie le dossier du site.");
    }
   }catch(Exception ex){MessageBox.Show("Le site Wakfu n’a pas démarré.\r\n"+ex.Message,"Wakfu Atlas",MessageBoxButtons.OK,MessageBoxIcon.Error);}
   finally{gate.ReleaseMutex();}
  }
 }
}

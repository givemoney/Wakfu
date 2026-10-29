using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using System.Collections.Generic;

class LancerSwitcheur {
 const string Title="WAKFU — fenêtres de combat";
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern IntPtr FindWindow(string cls,string title);
 [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
 [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h,int n);
 [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr h);
 [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h,IntPtr pid);
 [DllImport("user32.dll")] static extern bool AttachThreadInput(uint from,uint to,bool attach);
 [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
 [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h,uint msg,IntPtr w,IntPtr l);
 [DllImport("user32.dll")] static extern bool DestroyIcon(IntPtr icon);
 [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr context);

 static bool Reveal(){
  IntPtr h=FindWindow(null,Title);if(h==IntPtr.Zero)return false;
  ShowWindow(h,IsIconic(h)?9:5);
  uint current=GetCurrentThreadId(),foreground=GetWindowThreadProcessId(GetForegroundWindow(),IntPtr.Zero),target=GetWindowThreadProcessId(h,IntPtr.Zero);
  List<uint> attached=new List<uint>();
  try {
   foreach(uint t in new uint[]{foreground,target})if(t!=0&&t!=current&&!attached.Contains(t)&&AttachThreadInput(current,t,true))attached.Add(t);
   BringWindowToTop(h);SetForegroundWindow(h);
  }finally{foreach(uint t in attached)AttachThreadInput(current,t,false);}
  return true;
 }
 [STAThread] static void Main(){
  Application.EnableVisualStyles();
  try{
   try{SetProcessDpiAwarenessContext(new IntPtr(-4));}catch{}
   if(Reveal())return;
   bool first;
   using(Mutex mutex=new Mutex(true,"Local\\WakfuBoardLanceurCombat",out first)){
    if(!first){for(int i=0;i<100;i++){if(Reveal())return;Thread.Sleep(50);}MessageBox.Show("Le switcher est en train de démarrer. Réessaie dans quelques secondes.","Fenêtres WAKFU");return;}
    try{SwitchContext context=new SwitchContext();Application.Run(context);}
    finally{mutex.ReleaseMutex();}
   }
  }catch(Exception ex){try{string errors=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"app","switcheur","lanceur-erreurs.log");Directory.CreateDirectory(Path.GetDirectoryName(errors));File.AppendAllText(errors,DateTime.Now.ToString("s")+" "+ex.ToString()+Environment.NewLine);}catch{}MessageBox.Show("Le switcher a rencontré une erreur : "+ex.Message,"Fenêtres WAKFU",MessageBoxButtons.OK,MessageBoxIcon.Error);}
 }

 class SwitchContext : ApplicationContext {
  readonly NotifyIcon tray;
  readonly System.Windows.Forms.Timer timer;
  readonly ToolStripMenuItem stateLine;
  readonly Process child;
  readonly Icon active=MakeIcon(Color.FromArgb(23,113,58)),paused=MakeIcon(Color.FromArgb(178,115,0)),failed=MakeIcon(Color.FromArgb(174,42,42)),starting=MakeIcon(Color.FromArgb(95,105,120));
  readonly string root=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"app"),log;
  readonly object logLock=new object();
  bool requestedQuit,disposed;
  string previousState="";
  public SwitchContext(){
   string logFolder=Path.Combine(root,"switcheur");Directory.CreateDirectory(logFolder);
   log=Path.Combine(logFolder,"lancement-"+DateTime.Now.ToString("yyyyMMdd-HHmmss")+".log");
   File.WriteAllText(log,"Démarrage du switcher "+DateTime.Now.ToString("s")+Environment.NewLine);
   stateLine=new ToolStripMenuItem("Démarrage…");stateLine.Enabled=false;
   ContextMenuStrip menu=new ContextMenuStrip();menu.Items.Add(stateLine);menu.Items.Add(new ToolStripSeparator());
   menu.Items.Add("Afficher le panneau",null,(s,e)=>{if(!Reveal())tray.ShowBalloonTip(3000,"Fenêtres WAKFU","Le panneau est en cours de démarrage.",ToolTipIcon.Info);});
   menu.Items.Add("Quitter le switcher",null,(s,e)=>{requestedQuit=true;ClosePanel();});
   tray=new NotifyIcon{Icon=starting,Text="Fenêtres WAKFU — démarrage",Visible=true,ContextMenuStrip=menu};
   tray.DoubleClick+=(s,e)=>Reveal();
   ProcessStartInfo launch=new ProcessStartInfo(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"runtime","python.exe"),"\""+Path.Combine(root,"SwitcheurWakfu.py")+"\"");
   launch.UseShellExecute=false;launch.CreateNoWindow=true;launch.WindowStyle=ProcessWindowStyle.Hidden;
   launch.WorkingDirectory=root;launch.RedirectStandardError=true;
   child=new Process{StartInfo=launch};
   child.ErrorDataReceived+=(s,e)=>{if(e.Data!=null)try{lock(logLock)File.AppendAllText(log,e.Data+Environment.NewLine);}catch(IOException){}catch(UnauthorizedAccessException){}};
   child.Start();child.BeginErrorReadLine();
   timer=new System.Windows.Forms.Timer{Interval=700};timer.Tick+=(s,e)=>Tick();timer.Start();
  }
  void ClosePanel(){
   IntPtr h=FindWindow(null,Title);
   if(h!=IntPtr.Zero)PostMessage(h,0x0010,IntPtr.Zero,IntPtr.Zero);
   stateLine.Text="Fermeture…";tray.Text="Fenêtres WAKFU — fermeture";tray.Icon=paused;
  }
  void Tick(){
   try{
    if(child.HasExited){
     timer.Stop();child.WaitForExit();
     if(child.ExitCode!=0)MessageBox.Show("Le switcher s’est arrêté après une erreur.\r\nLes détails sont dans :\r\n"+log,"Fenêtres WAKFU",MessageBoxButtons.OK,MessageBoxIcon.Error);

     ExitThread();return;
    }

    if(requestedQuit){ClosePanel();return;}
    string path=Path.Combine(root,"coordination-fenetres","switcher.json");
    if(!File.Exists(path))return;
    var status=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(path));
    if(Convert.ToInt32(status["pid"])!=child.Id)return;
    string state=status.ContainsKey("app_state")?Convert.ToString(status["app_state"]):"starting";
    string text=status.ContainsKey("status")?Convert.ToString(status["status"]):"Démarrage…";
    if(status.ContainsKey("updated_utc")){
     double now=(DateTime.UtcNow-new DateTime(1970,1,1,0,0,0,DateTimeKind.Utc)).TotalSeconds;
     if(now-Convert.ToDouble(status["updated_utc"])>8){state="unresponsive";text="Le panneau ne répond plus";}
    }
    stateLine.Text=text;
    string tip="Fenêtres WAKFU — "+text;tray.Text=tip.Length>63?tip.Substring(0,63):tip;
    tray.Icon=state=="running"?active:state=="error"||state=="unresponsive"?failed:state=="starting"?starting:paused;
    if((state=="error"||state=="unresponsive")&&state!=previousState){
     string issue=status.ContainsKey("issue")?Convert.ToString(status["issue"]):"";
     tray.ShowBalloonTip(5000,"Fenêtres WAKFU : automatique arrêté",issue.Length>0?issue:"Ouvre le panneau pour vérifier son état.",ToolTipIcon.Warning);
    }
    previousState=state;
   }catch(IOException){}catch(InvalidOperationException){}catch(ArgumentException){}
   catch(Exception ex){stateLine.Text="État indisponible — affiche le panneau";tray.Icon=failed;if(previousState!="status-error"){try{lock(logLock)File.AppendAllText(log,ex.ToString()+Environment.NewLine);}catch(IOException){}previousState="status-error";}}
  }
  static Icon MakeIcon(Color color){
   using(Bitmap bitmap=new Bitmap(32,32)){
    using(Graphics g=Graphics.FromImage(bitmap)){
     g.SmoothingMode=System.Drawing.Drawing2D.SmoothingMode.AntiAlias;g.Clear(Color.Transparent);
     using(Brush brush=new SolidBrush(color))g.FillEllipse(brush,1,1,30,30);
     using(Font font=new Font("Segoe UI",16,FontStyle.Bold,GraphicsUnit.Pixel))
     using(StringFormat format=new StringFormat{Alignment=StringAlignment.Center,LineAlignment=StringAlignment.Center})
      g.DrawString("W",font,Brushes.White,new RectangleF(0,0,32,31),format);
    }
    IntPtr h=bitmap.GetHicon();try{using(Icon borrowed=Icon.FromHandle(h))return (Icon)borrowed.Clone();}finally{DestroyIcon(h);}
   }
  }
  protected override void Dispose(bool disposing){
   if(disposing&&!disposed){disposed=true;if(timer!=null){timer.Stop();timer.Dispose();}if(tray!=null){ContextMenuStrip menu=tray.ContextMenuStrip;tray.ContextMenuStrip=null;tray.Visible=false;tray.Dispose();if(menu!=null)menu.Dispose();}if(child!=null)child.Dispose();active.Dispose();paused.Dispose();failed.Dispose();starting.Dispose();}
   base.Dispose(disposing);
  }
 }
}

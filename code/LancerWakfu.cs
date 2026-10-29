using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Windows.Forms;

class LancerWakfu {
 const string Launcher=@"E:\Ankama\Ankama Launcher\Ankama Launcher.exe";
 const string GameJava=@"E:\Ankama\Wakfu\jre\bin\javaw.exe";
 static int CountInstances(){
  int count=0;
  foreach(Process p in Process.GetProcessesByName("javaw")){
   using(p){
    try { if(string.Equals(p.MainModule.FileName,GameJava,StringComparison.OrdinalIgnoreCase))count++; }
    catch { throw new Exception("Impossible de compter les instances WAKFU. Lance ce raccourci avec les mêmes droits que le jeu."); }
   }
  }
  return count;
 }
 [STAThread] static int Main(string[] args){
  if(args.Length==1&&args[0]=="--check")return File.Exists(Launcher)&&File.Exists(GameJava)?0:1;
  bool first;
  using(Mutex mutex=new Mutex(true,"Local\\WakfuBoardLancerQuatre",out first)){
   if(!first)return 0;
   try{
    if(!File.Exists(Launcher)||!File.Exists(GameJava))throw new Exception("Le Launcher ou WAKFU est introuvable sur E:\\Ankama.");
    int current=CountInstances();
    if(current>=4){MessageBox.Show("Quatre instances WAKFU sont déjà ouvertes.","WAKFU");return 0;}
    while(current<4){
     Process.Start(new ProcessStartInfo(Launcher,"\"zaap://app/games/game/wakfu/main?launch\""){UseShellExecute=true,WorkingDirectory=Path.GetDirectoryName(Launcher)});
     Stopwatch wait=Stopwatch.StartNew();
     int next=current;
     while(next<=current&&wait.ElapsedMilliseconds<90000){Thread.Sleep(500);next=CountInstances();}
     if(next<=current)throw new Exception("Le Launcher n'a pas ouvert de nouvelle instance. Vérifie ses éventuels messages (connexion, mise à jour), puis relance ce raccourci.");
     current=next;
     if(current<4)Thread.Sleep(1500);
    }
    return 0;
   }catch(Exception ex){MessageBox.Show(ex.Message,"Lancer 4 WAKFU",MessageBoxButtons.OK,MessageBoxIcon.Information);return 1;}
   finally{mutex.ReleaseMutex();}
  }
 }
}

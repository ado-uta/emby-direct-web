"""Rebuildable libmedia 1.3.1 AudioBuffer seek scheduling patch."""
from pathlib import Path

def patch_audio(text):
    replacements=[
        ('case"clear":this.queue.forEach((e=>{e.disconnect()})),this.queue.length=0;', 'case"clear":this.queue.forEach((e=>{e.onended=null;try{e.stop()}catch(_){}e.disconnect()})),this.queue.length=0,this.startTime=0;'),
        ('0===this.startTime&&(this.startTime=this.context.currentTime),t.start(this.startTime)', 'this.startTime=Math.max(this.startTime,this.context.currentTime),t.start(this.startTime)'),
        ('disconnect(){for(let e=0;e<this.queue.length;e++)this.queue[e].disconnect();this.dest=null,this.queue.length=0}', 'disconnect(){for(let e=0;e<this.queue.length;e++){const t=this.queue[e];t.onended=null;try{t.stop()}catch(_){}t.disconnect()}this.dest=null,this.queue.length=0,this.startTime=0}')
    ]
    for before,after in replacements:
        assert text.count(before)==1,'Audio patch anchor changed'
        text=text.replace(before,after)
    return text

if __name__=='__main__':
    path=Path(__file__).resolve().parents[1]/'web/vendor/avplayer.js'
    path.write_text(patch_audio(path.read_text(encoding='utf-8')),encoding='utf-8')

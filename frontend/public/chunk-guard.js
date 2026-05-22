(function(){
  var triggered=false;

  function isChunk(msg,err){
    return (err&&err.name==='ChunkLoadError')||
           String(msg||'').indexOf('Loading chunk')!==-1||
           String(msg||'').indexOf('ChunkLoadError')!==-1;
  }

  function hideAndReload(){
    if(triggered)return;
    triggered=true;
    try{
      document.querySelectorAll('nextjs-portal').forEach(function(n){n.remove();});
      var s=document.createElement('style');
      s.textContent='body,nextjs-portal,#__next-build-watcher{visibility:hidden!important;display:none!important}';
      (document.head||document.documentElement).appendChild(s);
      var mo=new MutationObserver(function(ms){
        ms.forEach(function(m){
          m.addedNodes.forEach(function(n){
            if(n.nodeName&&n.nodeName.toLowerCase()==='nextjs-portal'){n.remove();}
          });
        });
      });
      mo.observe(document.documentElement,{childList:true,subtree:true});
    }catch(e){}
    setTimeout(function(){window.location.reload();},50);
  }

  var _oe=window.onerror;
  window.onerror=function(msg,src,line,col,err){
    if(isChunk(msg,err)){hideAndReload();return true;}
    return _oe?_oe.apply(this,arguments):false;
  };
  window.addEventListener('unhandledrejection',function(e){
    var r=e.reason;
    if(r&&(r.name==='ChunkLoadError'||String(r.message||'').indexOf('Loading chunk')!==-1)){
      e.preventDefault();hideAndReload();
    }
  });
})();

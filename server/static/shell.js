/* 369 Studio — shared shell: left rail + top pill-nav + Supabase auth/session + api() */
(function(){
  var SB = window.supabase.createClient(window.SUPA_URL, window.SUPA_ANON);
  var TOKEN=null, ME=null;
  var NAV=[
    {id:"agent",  label:"Agent",       href:"/"},
    {id:"employees",label:"AI Employees",href:"/employees"},
    {id:"studio", label:"Studio",      href:"/creator"},
    {id:"agency", label:"Agency",      href:"/agency"},
    {id:"apps",   label:"Apps",        href:"/apps"},
    {id:"feed",   label:"Feed",        href:"/feed"},
    {id:"watch",  label:"Watch",       href:"/watch"}
  ];
  function initials(n){n=(n||"369").trim();var p=n.split(/[@\s]/)[0];return (p[0]||"3").toUpperCase();}
  function railHTML(){
    return '<div class="rail">'
      +'<div class="burger">☰</div>'
      +'<div class="ava" id="rail-ava">3</div>'
      +'<a class="ico" href="/creator" title="New">＋</a>'
      +'<a class="ico" href="/apps" title="Apps">🔍</a>'
      +'<a class="ico" href="/watch" title="Library">▦</a>'
      +'</div>';
  }
  function topHTML(active, seg){
    var nav=NAV.map(function(n){return '<a href="'+n.href+'" class="'+(n.id===active?'on':'')+'">'+n.label+'</a>';}).join('');
    return '<div class="topbar">'
      +'<div class="brand"><a class="logo" href="/">369<b>STUDIO</b></a>'+(seg?'<span class="seg">'+seg+'</span>':'')+'</div>'
      +'<nav class="nav">'+nav+'</nav>'
      +'<div class="top-actions">'
      +'<span class="heart">♡</span>'
      +'<a class="wallet" id="wallet" href="/dashboard">— cr</a>'
      +'<a class="ava-sm" id="ava" href="/dashboard">3</a>'
      +'</div></div>';
  }
  function H(){return {'Content-Type':'application/json','Authorization':'Bearer '+TOKEN};}
  async function api(path, opts){
    opts=opts||{}; opts.headers=Object.assign(H(), opts.headers||{});
    var r=await fetch(path,opts); if(!r.ok){var t;try{t=(await r.json()).detail;}catch(e){t=r.status;} throw new Error(t);} return r.json();
  }
  async function loadMe(){ try{ ME=await api('/api/me'); var w=document.getElementById('wallet'); if(w)w.textContent=(ME.wallet||0).toLocaleString()+' cr';
    var a=document.getElementById('ava'),ra=document.getElementById('rail-ava'),ini=initials(ME.name||''); if(a)a.textContent=ini; if(ra)ra.textContent=ini;
  }catch(e){} }

  var Shell={
    sb:SB, api:api, get token(){return TOKEN;}, get me(){return ME;},
    async mount(active, opts){
      opts=opts||{};
      var s=(await SB.auth.getSession()).data.session;
      // render frame chrome
      var host=document.getElementById('shell'); if(host){ host.innerHTML=railHTML()+topHTML(active, opts.seg||''); }
      if(!s){ if(opts.protected!==false){ location.href='/?next='+encodeURIComponent(location.pathname+location.search); return false;} return false; }
      TOKEN=s.access_token; await loadMe(); if(opts.onReady) opts.onReady();
      return true;
    },
    async signIn(email,pass){ var r=await SB.auth.signInWithPassword({email:email.trim(),password:pass}); if(r.error)throw new Error(r.error.message); return r; },
    async signUp(email,pass){ var r=await SB.auth.signUp({email:email.trim(),password:pass}); if(r.error)throw new Error(r.error.message); return r; },
    async signOut(){ await SB.auth.signOut(); location.href='/'; }
  };
  window.Shell=Shell;
})();

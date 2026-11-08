/* Training — общий скрипт: тема, блик за курсором, «капля» в навигации, главная страница и связка с тренажёрами. */
(function(){
  var root=document.documentElement;
  var store={
    get:function(k){try{return localStorage.getItem(k)}catch(e){return null}},
    set:function(k,v){try{if(v==null)localStorage.removeItem(k);else localStorage.setItem(k,v)}catch(e){}}
  };
  var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;

  var TOPICS=[
    {id:'limits',key:'limits-progress-v1',total:130,title:'Пределы'},
    {id:'derivatives',key:'deriv-progress-v1',total:116,title:'Производные'},
    {id:'integrals',key:'integrals-progress-v1',total:161,title:'Интегралы'}
  ];
  function plural(n,one,few,many){var a=n%10,b=n%100;return a===1&&b!==11?one:(a>=2&&a<=4&&(b<12||b>14)?few:many)}
  function solved(t){
    try{var o=JSON.parse(store.get(t.key)||'{}')||{};return Object.keys(o).filter(function(k){return o[k]}).length}catch(e){return 0}
  }

  /* ---------- тема: как в системе → светлая → тёмная ---------- */
  var THEME_KEY='training-theme';
  var LABEL={system:'Тема: как в системе',light:'Тема: светлая',dark:'Тема: тёмная'};
  var themeBtn=document.getElementById('themeBtn');
  var theme=store.get(THEME_KEY);
  if(theme!=='light'&&theme!=='dark')theme='system';
  else root.setAttribute('data-theme',theme);
  function paintThemeBtn(){if(!themeBtn)return;themeBtn.dataset.mode=theme;themeBtn.setAttribute('aria-label',LABEL[theme]);themeBtn.title=LABEL[theme]}
  paintThemeBtn();
  if(themeBtn)themeBtn.addEventListener('click',function(){
    theme={system:'light',light:'dark',dark:'system'}[theme];
    if(theme==='system'){root.removeAttribute('data-theme');store.set(THEME_KEY,null)}
    else{root.setAttribute('data-theme',theme);store.set(THEME_KEY,theme)}
    paintThemeBtn();
  });

  /* ---------- блик на стекле следует за курсором ---------- */
  var sheenEl=null,sheenX=0,sheenY=0,raf=0;
  document.addEventListener('pointermove',function(e){
    if(e.pointerType==='touch'||!e.target.closest)return;
    var el=e.target.closest('[data-sheen]');if(!el)return;
    sheenEl=el;sheenX=e.clientX;sheenY=e.clientY;
    if(!raf)raf=requestAnimationFrame(function(){raf=0;var r=sheenEl.getBoundingClientRect();
      sheenEl.style.setProperty('--mx',(sheenX-r.left)+'px');sheenEl.style.setProperty('--my',(sheenY-r.top)+'px')});
  },{passive:true});

  /* ---------- жидкая «капля» под активной вкладкой ---------- */
  var nav=document.querySelector('.seg-nav');
  var drop=nav&&nav.querySelector('.seg-nav__drop');
  function placeDrop(target,animate){
    if(!drop)return;
    var cur=target||nav.querySelector('[aria-current="page"]');
    if(!cur){drop.style.opacity='0';return}
    if(!animate){nav.classList.add('no-anim')}
    drop.style.opacity='1';
    drop.style.width=cur.offsetWidth+'px';
    drop.style.transform='translateX('+cur.offsetLeft+'px)';
    if(animate&&!reduce){drop.classList.remove('squash');void drop.offsetWidth;drop.classList.add('squash')}
    if(!animate){void drop.offsetWidth;requestAnimationFrame(function(){nav.classList.remove('no-anim')})}
    var l=cur.offsetLeft,r=l+cur.offsetWidth;
    if(l<nav.scrollLeft||r>nav.scrollLeft+nav.clientWidth)nav.scrollTo({left:l-16,behavior:animate&&!reduce?'smooth':'auto'});
  }
  if(nav){
    placeDrop(null,false);
    window.addEventListener('resize',function(){placeDrop(null,false)});
    if(document.fonts&&document.fonts.ready)document.fonts.ready.then(function(){placeDrop(null,false)});
  }

  var isTrainer=!!document.querySelector('.wrap > aside');
  if(isTrainer)initTrainer();else if(document.getElementById('views'))initHome();

  /* ================= страница тренажёра ================= */
  function initTrainer(){
    document.querySelectorAll('header.top,.wrap>aside,#main').forEach(function(el){el.setAttribute('data-sheen','')});
    // переход между тренажёрами: капля сначала перетекает, потом открывается страница
    if(nav)nav.addEventListener('click',function(e){
      var a=e.target.closest('a[href]');
      if(!a||a.getAttribute('aria-current')==='page'||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button!==0||reduce)return;
      e.preventDefault();placeDrop(a,true);
      setTimeout(function(){location.href=a.href},260);
    });
    // сброс прогресса без системного confirm(): второе нажатие подтверждает
    var rb=document.getElementById('resetBtn');
    if(rb){
      var armed=false,timer=0,label=rb.textContent;
      rb.onclick=function(){
        if(!armed){armed=true;rb.textContent='Точно сбросить? Нажми ещё раз';rb.classList.add('danger');
          timer=setTimeout(function(){armed=false;rb.textContent=label;rb.classList.remove('danger')},4000);return}
        clearTimeout(timer);armed=false;rb.classList.remove('danger');
        try{if(typeof done==='object'&&done){Object.keys(done).forEach(function(k){delete done[k]})}
          if(typeof save==='function')save();if(typeof render==='function')render()}catch(e){}
        rb.textContent='Прогресс сброшен';setTimeout(function(){rb.textContent=label},2200);
      };
    }
  }

  /* ================= главная ================= */
  function initHome(){
    var views=[].slice.call(document.querySelectorAll('#views > [data-view]'));
    var links=[].slice.call(document.querySelectorAll('.seg-nav a[data-view]'));
    var names=views.map(function(v){return v.dataset.view});
    function show(animate){
      var h=(location.hash||'').slice(1);
      var view=names.indexOf(h)>=0?h:names[0];
      views.forEach(function(v){v.hidden=v.dataset.view!==view});
      links.forEach(function(a){if(a.dataset.view===view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
      placeDrop(null,animate);
      var title={trainers:'Training',materials:'Материалы · Training',about:'О сайте · Training'}[view];
      if(title)document.title=title;
    }
    show(false);
    window.addEventListener('hashchange',function(){show(true);window.scrollTo({top:0,behavior:'auto'})});

    // прогресс на карточках тем
    function paintProgress(){
      TOPICS.forEach(function(t){
        var card=document.querySelector('.topic[data-topic="'+t.id+'"]');if(!card)return;
        var n=solved(t),pct=Math.min(100,Math.round(100*n/t.total));
        card.querySelector('.progress__bar i').style.width=pct+'%';
        card.querySelector('.progress__txt').textContent=n?('Решено '+n+' из '+t.total+' · '+pct+'%'):'Ещё не начато · '+t.total+' '+plural(t.total,'задача','задачи','задач');
        var go=card.querySelector('.topic__go');if(go)go.firstChild.textContent=n?'Продолжить':'Открыть тренажёр';
      });
    }
    paintProgress();
    window.addEventListener('pageshow',paintProgress);
    window.addEventListener('storage',paintProgress);

    // сброс всего прогресса (вкладка «О сайте»)
    var rAll=document.getElementById('resetAll');
    if(rAll){
      var armed=false,timer=0,label=rAll.textContent;
      rAll.addEventListener('click',function(){
        if(!armed){armed=true;rAll.textContent='Точно? Нажми ещё раз';rAll.classList.add('is-armed');
          timer=setTimeout(function(){armed=false;rAll.textContent=label;rAll.classList.remove('is-armed')},4000);return}
        clearTimeout(timer);armed=false;rAll.classList.remove('is-armed');
        TOPICS.forEach(function(t){store.set(t.key,null)});paintProgress();
        rAll.textContent='Прогресс сброшен';setTimeout(function(){rAll.textContent=label},2200);
      });
    }

    // линза с примерами из тренажёров
    var lens=document.querySelector('.lens');
    if(lens){
      var slides=[].slice.call(lens.querySelectorAll('.ex')),dots=[].slice.call(lens.querySelectorAll('.lens__dots button'));
      var i=0,timer2=0,paused=false;
      function go(k){
        i=(k+slides.length)%slides.length;
        slides.forEach(function(s,j){s.classList.toggle('is-on',j===i);s.setAttribute('aria-hidden',String(j!==i))});
        dots.forEach(function(d,j){d.setAttribute('aria-pressed',String(j===i))});
      }
      function tick(){clearTimeout(timer2);if(reduce)return;timer2=setTimeout(function(){if(!paused&&!document.hidden)go(i+1);tick()},6500)}
      dots.forEach(function(d,j){d.addEventListener('click',function(){go(j);tick()})});
      lens.addEventListener('pointerenter',function(){paused=true});
      lens.addEventListener('pointerleave',function(){paused=false});
      lens.addEventListener('focusin',function(){paused=true});
      lens.addEventListener('focusout',function(){paused=false});
      go(0);tick();
    }
  }
})();

(() => {
  const canvas = document.createElement('canvas');
  canvas.id = 'bg';
  document.body.prepend(canvas);
  const ctx = canvas.getContext('2d');
  let dpr = Math.max(1, window.devicePixelRatio || 1);

  // Respect reduced motion
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce) return;

  const state = {
    w: 0, h: 0, t: 0,
    particles: [],
    density: 0.00018, // particles per pixel
    speed: 0.6,
    scale: 0.0025,
    hueA: 208,
    hueB: 162,
  };

  function resize(){
    const { innerWidth, innerHeight } = window;
    state.w = innerWidth; state.h = innerHeight;
    canvas.width = Math.floor(state.w * dpr);
    canvas.height = Math.floor(state.h * dpr);
    canvas.style.width = state.w + 'px';
    canvas.style.height = state.h + 'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
    seed();
  }

  function rand(a,b){return a + Math.random()*(b-a)}

  function seed(){
    const target = Math.floor(state.w * state.h * state.density);
    const arr = [];
    for(let i=0;i<target;i++){
      arr.push({
        x: Math.random()*state.w,
        y: Math.random()*state.h,
        vx: 0, vy: 0,
        life: rand(200, 800),
        age: rand(0, 800),
      });
    }
    state.particles = arr;
  }

  function field(x,y,t){
    // Smooth pseudo-flow using trigs; avoids heavy noise libs
    const s = state.scale;
    const a = Math.sin((x*s) + t*0.0017) + Math.cos((y*s)*0.9 - t*0.0013);
    const b = Math.cos((y*s) + t*0.0011) - Math.sin((x*s)*1.1 + t*0.0019);
    const angle = Math.atan2(b, a);
    return angle;
  }

  function step(dt){
    const { w,h, particles, speed } = state;
    for(const p of particles){
      const ang = field(p.x, p.y, state.t);
      p.vx = Math.cos(ang) * speed;
      p.vy = Math.sin(ang) * speed;
      p.x += p.vx;
      p.y += p.vy;
      p.age++;
      if (p.x < -5) p.x = w+5; if (p.x > w+5) p.x = -5;
      if (p.y < -5) p.y = h+5; if (p.y > h+5) p.y = -5;
      if (p.age > p.life){
        p.x = Math.random()*w; p.y = Math.random()*h; p.age = 0; p.life = rand(200, 800);
      }
    }
  }

  function draw(){
    const g = ctx;
    const { w,h, particles, t } = state;
    // Fade the frame slightly for trails
    g.fillStyle = 'rgba(7,16,24,0.08)';
    g.fillRect(0,0,w,h);

    const hue = state.hueA + (Math.sin(t*0.0006)+1)*0.5*(state.hueB - state.hueA);
    g.globalCompositeOperation = 'lighter';
    g.lineWidth = 1.0;
    for(const p of particles){
      const alpha = 0.08 + 0.22*Math.sin((p.age/ p.life) * Math.PI);
      g.strokeStyle = `hsla(${hue}, 82%, 62%, ${alpha})`;
      g.beginPath();
      g.moveTo(p.x, p.y);
      g.lineTo(p.x - p.vx*2.5, p.y - p.vy*2.5);
      g.stroke();
    }
    g.globalCompositeOperation = 'source-over';
  }

  let last = performance.now();
  function loop(now){
    const dt = Math.min(50, now - last); last = now;
    state.t += dt;
    step(dt);
    draw();
    requestAnimationFrame(loop);
  }

  window.addEventListener('resize', resize, {passive:true});
  resize();
  requestAnimationFrame(loop);
})();

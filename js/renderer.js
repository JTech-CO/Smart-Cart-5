/* Smart-Cart-5 native WebGL2 solid viewer. No CDN or account/network dependency.
 * Exact OCC tessellation + GGX shading, procedural finishes, studio shadows and decals.
 * Orbit is Z-up, includes negative elevation. Ground is culled AND disabled below
 * the assembly horizon: it cannot occlude an underside inspection.
 */
'use strict';
window.D5Renderer=(()=>{
 const V={add:(a,b)=>a.map((v,i)=>v+b[i]),sub:(a,b)=>a.map((v,i)=>v-b[i]),mul:(a,s)=>a.map(x=>x*s),dot:(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0),cross:(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],norm:a=>{const l=Math.hypot(...a)||1;return a.map(x=>x/l)}};
 const M={mul:(a,b)=>{let o=Array(16).fill(0);for(let j=0;j<4;j++)for(let i=0;i<4;i++)for(let k=0;k<4;k++)o[j*4+i]+=a[k*4+i]*b[j*4+k];return o},point:(a,p)=>[0,1,2,3].map(i=>a[i]*p[0]+a[i+4]*p[1]+a[i+8]*p[2]+a[i+12]),perspective:(f,a,n,z)=>{const q=1/Math.tan(f/2);return[q/a,0,0,0,0,q,0,0,0,0,(z+n)/(n-z),-1,0,0,2*z*n/(n-z),0]},ortho:(l,r,b,t,n,f)=>[2/(r-l),0,0,0,0,2/(t-b),0,0,0,0,-2/(f-n),0,-(r+l)/(r-l),-(t+b)/(t-b),-(f+n)/(f-n),1],look:(e,t)=>{const z=V.norm(V.sub(e,t)),x=V.norm(V.cross([0,0,1],z)),y=V.cross(z,x);return[x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-V.dot(x,e),-V.dot(y,e),-V.dot(z,e),1]}};
 const col=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16)/255);
 const VS=`#version 300 es
 precision highp float;layout(location=0)in vec3 p;layout(location=1)in vec3 n;
 uniform mat4 vp,lightVP;out vec3 P,N;out vec4 S;
 void main(){P=p;N=n;S=lightVP*vec4(p,1.);gl_Position=vp*vec4(p,1.);}`;
 const FS=`#version 300 es
 precision highp float;in vec3 P,N;in vec4 S;out vec4 frag;
 uniform vec3 color,eye,pick,origin,right,up;uniform vec2 labelSize;
 uniform float metal,rough,alpha,selected,fade;uniform int mode,surface,hasLabel,isFloor,grid;
 uniform sampler2D shadowMap,labelMap;
 const float PI=3.14159265359;
 float hash(vec3 p){p=fract(p*.1031);p+=dot(p,p.yzx+33.33);return fract((p.x+p.y)*p.z);}
 float shadow(vec3 n,vec3 l){vec3 p=S.xyz/S.w*.5+.5;if(any(lessThan(p,vec3(0)))||any(greaterThan(p,vec3(1))))return 1.;float s=0.;float bias=max(.0025*(1.-max(dot(n,l),0.)),.0010);for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)s+=p.z-bias<=texture(shadowMap,p.xy+vec2(x,y)/2048.).r?1.:.2;return s/9.;}
 vec3 fres(float c,vec3 f){return f+(1.-f)*pow(clamp(1.-c,0.,1.),5.);}
 vec3 brdf(vec3 n,vec3 v,vec3 l,vec3 base,float m,float r){vec3 h=normalize(v+l);float nv=max(dot(n,v),.001),nl=max(dot(n,l),0.),nh=max(dot(n,h),0.),vh=max(dot(v,h),0.);float a=r*r,a2=a*a,d=nh*nh*(a2-1.)+1.,D=a2/(PI*d*d+.00001),k=(r+1.)*(r+1.)/8.;float G=nv/(nv*(1.-k)+k)*nl/(nl*(1.-k)+k);vec3 F=fres(vh,mix(vec3(.04),base,m));return ((1.-F)*(1.-m)*base/PI+D*G*F/(4.*nv*max(nl,.001)+.0001))*nl;}
 vec3 studio(vec3 r,float ro){float a=pow(max(dot(r,normalize(vec3(-.4,-.7,1.))),0.),mix(55.,5.,ro));float b=pow(max(dot(r,normalize(vec3(.7,.5,.8))),0.),mix(40.,4.,ro));float c=pow(max(dot(r,normalize(vec3(-.7,.3,-.5))),0.),7.);return vec3(.38,.43,.49)+vec3(1.4,1.43,1.48)*a+vec3(.9,1.,1.13)*b+vec3(.16)*c;}
 vec3 aces(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
 void main(){if(mode==1){frag=vec4(pick,1);return;}if(mode==2){frag=vec4(1);return;}
 vec3 n=normalize(N);if(!gl_FrontFacing)n=-n;vec3 v=normalize(eye-P);vec3 base=pow(color,vec3(2.2));float ro=max(.13,rough);
 if(hasLabel==1){vec3 d=P-origin;vec2 uv=vec2(dot(d,right),dot(d,up))/labelSize+.5;vec4 t=texture(labelMap,vec2(uv.x,1.-uv.y));base=pow(t.rgb,vec3(2.2));}
 else if(surface>0){float g=hash(floor(P*6000.));base*=.994+.012*g;
   if(surface==3){float b=sin(P.z*22000.+sin(P.x*7000.))*sin(P.y*15000.);base*=.995+.005*b;}
   if(surface==2){float d=abs(sin((P.x+P.y)*290.))*abs(sin((P.x-P.y)*290.));base*=.9+.12*smoothstep(.3,.8,d);}
   if(surface==5&&abs(n.z)>.8){vec2 q=P.xy*50.;float k=floor(q.x)+floor(q.y);vec2 t=fract(q)-.5;float a=mod(k,2.)<1.?t.x+t.y:t.x-t.y;float b=mod(k,2.)<1.?t.x-t.y:t.x+t.y;float tread=exp(-a*a*250.)*(1.-smoothstep(.4,.7,abs(b)));base*=.82+.38*tread;n=normalize(n+vec3(-.12*a*exp(-a*a*250.),.1*a*exp(-a*a*250.),0.));}
   if(surface==4){float t=step(.965,fract(P.x*680.))*step(.5,fract(P.y*420.));base=mix(base,base*1.5,t*.18);}
 }
 vec3 l=normalize(vec3(-.5,-.9,1.5));float sh=shadow(n,l);
 if(isFloor==1){float v0=1.;if(grid==1){vec2 q=P.xy*10.;vec2 a=abs(fract(q-.5)-.5)/max(fwidth(q),vec2(.002));float line=1.-min(min(a.x,a.y),1.);base*=1.-line*.06;}float ao=exp(-dot(P.xy/vec2(.6,.42),P.xy/vec2(.6,.42))*2.3)*.08;vec3 c=vec3(.86,.88,.9)*(1.-ao)*(.88+.12*sh);frag=vec4(pow(c,vec3(1./2.2)),1.);return;}
 vec3 f0=mix(vec3(.04),base,metal),F=fres(max(dot(n,v),0.),f0);
 float hemi=.65+.25*max(n.z,0.);vec3 c=base*(1.-metal)*hemi*.61;
 c+=studio(reflect(-v,n),ro)*F*(.45+.32*(1.-ro));
 c+=brdf(n,v,l,base,metal,ro)*vec3(3.2,3.1,2.95)*sh;
 c+=brdf(n,v,normalize(vec3(.9,.65,.7)),base,metal,ro)*vec3(1.1,1.25,1.5);
 c+=brdf(n,v,normalize(vec3(-.1,.5,-1.)),base,metal,ro)*vec3(.45,.52,.6);
 if(selected>0.)c=mix(c,c+vec3(.03,.35,.42),.3)+vec3(.02,.22,.3)*pow(1.-max(dot(n,v),0.),3.);
 c=mix(c,vec3(.7),fade);frag=vec4(pow(aces(c*1.13),vec3(1./2.2)),alpha);
 }`;
 function shader(g,type,src){const s=g.createShader(type);g.shaderSource(s,src);g.compileShader(s);if(!g.getShaderParameter(s,g.COMPILE_STATUS))throw Error(g.getShaderInfoLog(s));return s}
 class Renderer{
 constructor(canvas,model,bytes){this.canvas=canvas;this.model=model;this.state={yaw:-.86,pitch:.47,distance:1.9,target:[-.015,0,.46],selection:'',floor:true,grid:true,covers:false,deck:true,wires:true,labels:false,accessories:false,wireKind:'all'};this.items=[];this.decals=[];this.invalid=true;this.shadowDirty=true;this.pickIds=new Map();this.idRefs=new Map();this.drawCalls=0;
 const g=this.gl=canvas.getContext('webgl2',{antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});if(!g)throw Error('WebGL 2를 사용할 수 없습니다. Chromium/Edge의 하드웨어 가속을 확인하세요.');
 this.program=g.createProgram();g.attachShader(this.program,shader(g,g.VERTEX_SHADER,VS));g.attachShader(this.program,shader(g,g.FRAGMENT_SHADER,FS));g.linkProgram(this.program);if(!g.getProgramParameter(this.program,g.LINK_STATUS))throw Error(g.getProgramInfoLog(this.program));g.useProgram(this.program);
 this.u={};for(const k of ['vp','lightVP','color','eye','pick','metal','rough','alpha','selected','fade','mode','surface','hasLabel','isFloor','grid','shadowMap','labelMap','origin','right','up','labelSize'])this.u[k]=g.getUniformLocation(this.program,k);
 g.uniform1i(this.u.shadowMap,0);g.uniform1i(this.u.labelMap,1);
 for(const q of model.geometry){if(!this.pickIds.has(q.ref)){const id=this.pickIds.size+1;this.pickIds.set(q.ref,id);this.idRefs.set(id,q.ref)}const arr=new Float32Array(bytes,q.offset,q.count*6);this.items.push(this.makeItem(q,arr,model.materials[q.material]));}
 // Ground front face only. Also automatically suppressed below the orbit horizon.
 const a=-8,b=8,z=-.004;this.floorItem=this.makeItem({ref:'__floor',category:'ground',count:6},new Float32Array([a,a,z,0,0,1,b,a,z,0,0,1,b,b,z,0,0,1,a,a,z,0,0,1,b,b,z,0,0,1,a,b,z,0,0,1]),{color:'#e5e9eb',metal:0,rough:1,surface:0});
 for(const d of model.decals){const r=V.mul(d.right,d.size[0]/2000),u=V.mul(d.up,d.size[1]/2000),c=d.center.map(v=>v/1000),n=V.norm(V.cross(d.right,d.up));const pts=[V.sub(V.sub(c,r),u),V.sub(V.add(c,r),u),V.add(V.add(c,r),u),V.add(V.sub(c,r),u)];const arr=[];for(const i of [0,1,2,0,2,3])arr.push(...pts[i],...n);const item=this.makeItem({ref:d.ref,category:model.components.find(c=>c.id===d.ref)?.category||'frame',count:6},new Float32Array(arr),{color:'#ffffff',metal:0,rough:.63,surface:0});item.label=d;item.tex=this.labelTexture(d);this.decals.push(item)}
 this.lightVP=M.mul(M.ortho(-1.05,1.05,-1.12,1.12,.1,5),M.look([-1.3,-2.1,3.4],[0,0,.4]));
 this.shadowF=g.createFramebuffer();this.shadowTex=g.createTexture();g.bindTexture(g.TEXTURE_2D,this.shadowTex);g.texImage2D(g.TEXTURE_2D,0,g.DEPTH_COMPONENT24,2048,2048,0,g.DEPTH_COMPONENT,g.UNSIGNED_INT,null);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.NEAREST);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.NEAREST);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_S,g.CLAMP_TO_EDGE);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_T,g.CLAMP_TO_EDGE);g.bindFramebuffer(g.FRAMEBUFFER,this.shadowF);g.framebufferTexture2D(g.FRAMEBUFFER,g.DEPTH_ATTACHMENT,g.TEXTURE_2D,this.shadowTex,0);g.drawBuffers([g.NONE]);g.readBuffer(g.NONE);if(g.checkFramebufferStatus(g.FRAMEBUFFER)!==g.FRAMEBUFFER_COMPLETE)throw Error('Shadow framebuffer incomplete');
 this.pickF=g.createFramebuffer();this.pickTex=g.createTexture();this.pickDepth=g.createRenderbuffer();g.bindFramebuffer(g.FRAMEBUFFER,null);g.enable(g.DEPTH_TEST);g.enable(g.CULL_FACE);g.cullFace(g.BACK);
 this.resize();this.events();this.animate=this.animate.bind(this);requestAnimationFrame(this.animate);this.observer=new ResizeObserver(()=>this.resize());this.observer.observe(canvas);
 }
 makeItem(q,arr,mat){const g=this.gl,vao=g.createVertexArray(),buf=g.createBuffer();g.bindVertexArray(vao);g.bindBuffer(g.ARRAY_BUFFER,buf);g.bufferData(g.ARRAY_BUFFER,arr,g.STATIC_DRAW);g.enableVertexAttribArray(0);g.vertexAttribPointer(0,3,g.FLOAT,false,24,0);g.enableVertexAttribArray(1);g.vertexAttribPointer(1,3,g.FLOAT,false,24,12);return{...q,vao,buf,mat:{...mat,color:col(mat.color)}}}
 labelTexture(d){const g=this.gl,c=document.createElement('canvas');c.width=768;c.height=Math.max(128,Math.round(768*d.size[1]/d.size[0]));const x=c.getContext('2d');x.fillStyle=d.bg;x.fillRect(0,0,c.width,c.height);x.fillStyle=d.ink;x.textAlign='center';x.textBaseline='middle';const s=Math.min(c.width/(d.title.length*.62+2),c.height*.31);x.font=`700 ${s}px Arial, sans-serif`;x.fillText(d.title,c.width/2,c.height*.37,c.width*.92);x.font=`500 ${Math.min(c.height*.18,c.width/(d.sub.length*.58+2))}px Arial, sans-serif`;x.fillText(d.sub,c.width/2,c.height*.72,c.width*.94);const t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,c);g.generateMipmap(g.TEXTURE_2D);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR_MIPMAP_LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_S,g.CLAMP_TO_EDGE);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_T,g.CLAMP_TO_EDGE);return t}
 resize(){const g=this.gl,dpr=Math.min(devicePixelRatio||1,1.8),w=Math.max(1,Math.floor(this.canvas.clientWidth*dpr)),h=Math.max(1,Math.floor(this.canvas.clientHeight*dpr));if(w===this.canvas.width&&h===this.canvas.height&&this.sized)return;this.canvas.width=w;this.canvas.height=h;g.bindTexture(g.TEXTURE_2D,this.pickTex);g.texImage2D(g.TEXTURE_2D,0,g.RGBA8,w,h,0,g.RGBA,g.UNSIGNED_BYTE,null);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.NEAREST);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.NEAREST);g.bindRenderbuffer(g.RENDERBUFFER,this.pickDepth);g.renderbufferStorage(g.RENDERBUFFER,g.DEPTH_COMPONENT24,w,h);g.bindFramebuffer(g.FRAMEBUFFER,this.pickF);g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,this.pickTex,0);g.framebufferRenderbuffer(g.FRAMEBUFFER,g.DEPTH_ATTACHMENT,g.RENDERBUFFER,this.pickDepth);g.bindFramebuffer(g.FRAMEBUFFER,null);this.sized=true;this.invalid=true}
 visible(it){const s=this.state;if(it.category==='covers'&&!s.covers)return false;if(it.category==='wires'&&!s.wires)return false;if(it.category==='accessories'&&!s.accessories)return false;if(!s.deck&&['CART-DECK','DECK-MAT'].includes(it.ref))return false;if(s.hiddenCategories?.includes(it.category))return false;return true}
 groundVisible(){return this.state.floor&&this.state.pitch>.035&&this.eye?.[2]>.03}
 matrices(){const s=this.state,c=Math.cos(s.pitch),aspect=this.canvas.width/this.canvas.height,distance=s.distance*Math.max(1,.96/aspect);this.eye=V.add(s.target,[Math.cos(s.yaw)*c*distance,Math.sin(s.yaw)*c*distance,Math.sin(s.pitch)*distance]);this.vp=M.mul(M.perspective(37*Math.PI/180,this.canvas.width/this.canvas.height,Math.max(.001,s.distance/1800),20),M.look(this.eye,s.target))}
 drawItem(it,mode){if(!this.visible(it))return;const g=this.gl,u=this.u,s=this.state,m=it.mat;if(mode===2&&(it.category==='covers'||it.label||it.category==='accessories'))return;
 const id=this.pickIds.get(it.ref)||0;g.uniform3fv(u.pick,[(id&255)/255,((id>>8)&255)/255,((id>>16)&255)/255]);g.uniform3fv(u.color,m.color);g.uniform1f(u.metal,m.metal);g.uniform1f(u.rough,m.rough);g.uniform1f(u.alpha,m.alpha??1);g.uniform1f(u.selected,s.selection===it.ref?1:0);
 const wkind=it.category==='wires'?this.model.connections.find(w=>w.id===it.ref)?.kind:null;g.uniform1f(u.fade,wkind&&s.wireKind!=='all'&&wkind!==s.wireKind?.68:0);g.uniform1i(u.surface,m.surface||0);g.uniform1i(u.hasLabel,it.label?1:0);g.uniform1i(u.isFloor,it.ref==='__floor'?1:0);
 if(it.label){const d=it.label;g.uniform3fv(u.origin,d.center.map(v=>v/1000));g.uniform3fv(u.right,d.right);g.uniform3fv(u.up,d.up);g.uniform2fv(u.labelSize,d.size.map(v=>v/1000));g.activeTexture(g.TEXTURE1);g.bindTexture(g.TEXTURE_2D,it.tex);g.activeTexture(g.TEXTURE0)}
 g.bindVertexArray(it.vao);g.drawArrays(g.TRIANGLES,0,it.count);this.drawCalls++;
 }
 pass(mode){const g=this.gl;g.uniform1i(this.u.mode,mode);g.uniformMatrix4fv(this.u.vp,false,mode===2?this.lightVP:this.vp);g.depthMask(true);g.disable(g.BLEND);g.enable(g.CULL_FACE);
 if(mode===0&&this.groundVisible())this.drawItem(this.floorItem,mode);
 for(const it of this.items)if(it.category!=='covers')this.drawItem(it,mode);
 if(mode===0){g.enable(g.POLYGON_OFFSET_FILL);g.polygonOffset(-1,-1);g.enable(g.CULL_FACE);for(const it of this.decals)this.drawItem(it,mode);g.disable(g.POLYGON_OFFSET_FILL);g.enable(g.CULL_FACE);g.enable(g.BLEND);g.blendFunc(g.SRC_ALPHA,g.ONE_MINUS_SRC_ALPHA);g.depthMask(false);for(const it of this.items.filter(i=>i.category==='covers').sort((a,b)=>{const mid=g=>g.bbox_mm.slice(0,3).map((x,i)=>(x+g.bbox_mm[i+3])/2000);return Math.hypot(...V.sub(mid(b),this.eye))-Math.hypot(...V.sub(mid(a),this.eye))}))this.drawItem(it,mode);g.depthMask(true);g.disable(g.BLEND)}
 }
 draw(pick=false){const g=this.gl;this.matrices();g.useProgram(this.program);g.uniform3fv(this.u.eye,this.eye);g.uniformMatrix4fv(this.u.lightVP,false,this.lightVP);g.uniform1i(this.u.grid,this.state.grid?1:0);this.drawCalls=0;
 if(pick){g.bindFramebuffer(g.FRAMEBUFFER,this.pickF);g.viewport(0,0,this.canvas.width,this.canvas.height);g.clearColor(0,0,0,1);g.clear(g.COLOR_BUFFER_BIT|g.DEPTH_BUFFER_BIT);this.pass(1);return}
 if(this.shadowDirty){g.activeTexture(g.TEXTURE0);g.bindTexture(g.TEXTURE_2D,null);g.bindFramebuffer(g.FRAMEBUFFER,this.shadowF);g.viewport(0,0,2048,2048);g.clear(g.DEPTH_BUFFER_BIT);this.pass(2);this.shadowDirty=false}
 g.bindFramebuffer(g.FRAMEBUFFER,null);g.viewport(0,0,this.canvas.width,this.canvas.height);g.clearColor(.935,.944,.95,1);g.clear(g.COLOR_BUFFER_BIT|g.DEPTH_BUFFER_BIT);g.activeTexture(g.TEXTURE0);g.bindTexture(g.TEXTURE_2D,this.shadowTex);this.pass(0);this.onframe?.();
 }
 pick(x,y){this.draw(true);const g=this.gl,r=this.canvas.getBoundingClientRect(),p=new Uint8Array(4);g.readPixels(Math.min(this.canvas.width-1,Math.max(0,Math.floor((x-r.left)*this.canvas.width/r.width))),Math.min(this.canvas.height-1,Math.max(0,Math.floor((r.bottom-y)*this.canvas.height/r.height))),1,1,g.RGBA,g.UNSIGNED_BYTE,p);g.bindFramebuffer(g.FRAMEBUFFER,null);this.invalid=true;return this.idRefs.get(p[0]+256*p[1]+65536*p[2])||''}
 project(point){if(!this.vp)return null;const p=M.point(this.vp,point.map(v=>v/1000));if(p[3]<=0)return null;const x=p[0]/p[3],y=p[1]/p[3];if(Math.abs(x)>1||Math.abs(y)>1)return null;return[(x*.5+.5)*this.canvas.clientWidth,(.5-y*.5)*this.canvas.clientHeight]}
 change(){this.invalid=true;this.shadowDirty=true}
 focus(ref){const g=this.model.geometry.filter(g=>g.ref===ref);if(!g.length)return;const lo=[0,1,2].map(i=>Math.min(...g.map(q=>q.bbox_mm[i]))),hi=[0,1,2].map(i=>Math.max(...g.map(q=>q.bbox_mm[i+3])));this.state.target=lo.map((x,i)=>(x+hi[i])/2000);this.state.distance=Math.max(.32,Math.hypot(...V.sub(hi,lo))/1000*2.35);this.state.selection=ref;this.state.pitch=ref.startsWith('SCMB')?-.28:.36;this.invalid=true}
 events(){const c=this.canvas,s=this.state;let pointers=new Map(),start=null,moved=0;const pan=(dx,dy)=>{const right=[-Math.sin(s.yaw),Math.cos(s.yaw),0],f=[Math.cos(s.yaw)*Math.sin(s.pitch),Math.sin(s.yaw)*Math.sin(s.pitch),-Math.cos(s.pitch)],k=s.distance*.0006;s.target=V.add(s.target,V.add(V.mul(right,dx*k),V.mul(f,dy*k)))};
 c.addEventListener('contextmenu',e=>e.preventDefault());c.addEventListener('pointerdown',e=>{c.focus();c.setPointerCapture(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);start=[e.clientX,e.clientY];moved=0});
 c.addEventListener('pointermove',e=>{if(!pointers.has(e.pointerId))return;const a=pointers.get(e.pointerId),b=[e.clientX,e.clientY],dx=b[0]-a[0],dy=b[1]-a[1];moved+=Math.hypot(dx,dy);if(pointers.size===2){const other=[...pointers].find(([id])=>id!==e.pointerId)[1];const old=Math.hypot(...V.sub(a,other)),now=Math.hypot(...V.sub(b,other));if(now>4)s.distance=Math.max(.12,Math.min(5,s.distance*old/now));pan(dx*.5,dy*.5)}else if(e.buttons===2||e.shiftKey)pan(dx,dy);else{s.yaw-=dx*.006;s.pitch=Math.max(-1.56,Math.min(1.56,s.pitch+dy*.006))}pointers.set(e.pointerId,b);this.invalid=true});
 c.addEventListener('pointerup',e=>{const single=pointers.size===1;pointers.delete(e.pointerId);if(single&&moved<5)this.onpick?.(this.pick(e.clientX,e.clientY))});c.addEventListener('pointercancel',e=>pointers.delete(e.pointerId));c.addEventListener('wheel',e=>{e.preventDefault();s.distance=Math.max(.12,Math.min(5,s.distance*Math.exp(e.deltaY*.001)));this.invalid=true},{passive:false});
 c.addEventListener('dblclick',e=>{const r=this.pick(e.clientX,e.clientY);if(r){this.focus(r);this.onpick?.(r)}});
 c.addEventListener('keydown',e=>{let handled=true;if(e.key==='ArrowLeft')s.yaw-=.1;else if(e.key==='ArrowRight')s.yaw+=.1;else if(e.key==='ArrowUp')s.pitch=Math.min(1.56,s.pitch+.1);else if(e.key==='ArrowDown')s.pitch=Math.max(-1.56,s.pitch-.1);else if(e.key==='+'||e.key==='=')s.distance*=.9;else if(e.key==='-')s.distance*=1.1;else if(e.key==='Home')this.onhome?.();else if(e.key==='Escape')this.onpick?.('');else handled=false;if(handled){e.preventDefault();this.invalid=true}});
 c.addEventListener('webglcontextlost',e=>{e.preventDefault();this.lost=true;this.onerror?.('GPU 컨텍스트가 해제됐습니다. 새로고침하여 모델을 다시 불러오세요.')});
 }
 animate(){if(this.invalid&&!this.lost&&!document.hidden){this.invalid=false;this.draw()}requestAnimationFrame(this.animate)}
 }
 return{Renderer,V,M};
})();

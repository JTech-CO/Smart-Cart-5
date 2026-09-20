#!/usr/bin/env python3
"""Render the production GLSL ES 3 shaders and OCC mesh in an EGL pbuffer.
This verifies the standalone shaders/scene, not a browser WebGL implementation.
Linux Mesa EGL/GLES2, NumPy and Pillow are test-only dependencies.
"""
from pathlib import Path
import os,re,json,math,ctypes as C
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];os.environ.setdefault('EGL_PLATFORM','surfaceless')
E=C.CDLL('libEGL.so.1');G=C.CDLL('libGL.so.1');I=C.c_int;U=C.c_uint;F=C.c_float;P=C.c_void_p

def bind(lib,n,ret,args):
 f=getattr(lib,n);f.restype=ret;f.argtypes=args;return f
for n,ret,args in [('eglGetDisplay',P,[P]),('eglInitialize',U,[P,C.POINTER(I),C.POINTER(I)]),('eglBindAPI',U,[U]),('eglChooseConfig',U,[P,C.POINTER(I),C.POINTER(P),I,C.POINTER(I)]),('eglCreatePbufferSurface',P,[P,P,C.POINTER(I)]),('eglCreateContext',P,[P,P,P,C.POINTER(I)]),('eglMakeCurrent',U,[P,P,P,P]),('eglGetError',U,[])]:bind(E,n,ret,args)
dpy=E.eglGetDisplay(None);ma,mi=I(),I();assert E.eglInitialize(dpy,C.byref(ma),C.byref(mi));assert E.eglBindAPI(0x30A0)
attrs=(I*17)(0x3033,1,0x3040,0x40,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,24,0x3038,0,0)
cfg=P();cnt=I();assert E.eglChooseConfig(dpy,attrs,C.byref(cfg),1,C.byref(cnt)) and cnt.value
W,H=1800,1300;surf=E.eglCreatePbufferSurface(dpy,cfg,(I*5)(0x3057,W,0x3056,H,0x3038));ctx=E.eglCreateContext(dpy,cfg,None,(I*3)(0x3098,3,0x3038));assert surf and ctx and E.eglMakeCurrent(dpy,surf,surf,ctx)
sigs={
 'glGetString':(C.c_char_p,[U]),'glGetError':(U,[]),'glCreateShader':(U,[U]),'glShaderSource':(None,[U,I,C.POINTER(C.c_char_p),C.POINTER(I)]),'glCompileShader':(None,[U]),'glGetShaderiv':(None,[U,U,C.POINTER(I)]),'glGetShaderInfoLog':(None,[U,I,C.POINTER(I),P]),'glCreateProgram':(U,[]),'glAttachShader':(None,[U,U]),'glLinkProgram':(None,[U]),'glGetProgramiv':(None,[U,U,C.POINTER(I)]),'glGetProgramInfoLog':(None,[U,I,C.POINTER(I),P]),'glUseProgram':(None,[U]),'glGetUniformLocation':(I,[U,C.c_char_p]),
 'glUniform1i':(None,[I,I]),'glUniform1f':(None,[I,F]),'glUniform2fv':(None,[I,I,P]),'glUniform3fv':(None,[I,I,P]),'glUniformMatrix4fv':(None,[I,I,U,P]),'glGenVertexArrays':(None,[I,C.POINTER(U)]),'glBindVertexArray':(None,[U]),'glGenBuffers':(None,[I,C.POINTER(U)]),'glBindBuffer':(None,[U,U]),'glBufferData':(None,[U,C.c_ssize_t,P,U]),'glEnableVertexAttribArray':(None,[U]),'glVertexAttribPointer':(None,[U,I,U,U,I,P]),
 'glGenTextures':(None,[I,C.POINTER(U)]),'glBindTexture':(None,[U,U]),'glActiveTexture':(None,[U]),'glTexImage2D':(None,[U,I,I,I,I,I,U,U,P]),'glTexParameteri':(None,[U,U,I]),'glGenerateMipmap':(None,[U]),'glGenFramebuffers':(None,[I,C.POINTER(U)]),'glBindFramebuffer':(None,[U,U]),'glFramebufferTexture2D':(None,[U,U,U,U,I]),'glCheckFramebufferStatus':(U,[U]),'glDrawBuffers':(None,[I,C.POINTER(U)]),'glReadBuffer':(None,[U]),
 'glEnable':(None,[U]),'glDisable':(None,[U]),'glCullFace':(None,[U]),'glViewport':(None,[I,I,I,I]),'glClearColor':(None,[F,F,F,F]),'glClear':(None,[U]),'glDrawArrays':(None,[U,I,I]),'glDepthMask':(None,[U]),'glBlendFunc':(None,[U,U]),'glPolygonOffset':(None,[F,F]),'glReadPixels':(None,[I,I,I,I,U,U,P]),'glFinish':(None,[])}
for n,(rt,args)in sigs.items():bind(G,n,rt,args)
src=(ROOT/'js/renderer.js').read_text();vs=re.search(r'const VS=`(.*?)`;',src,re.S).group(1);fs=re.search(r'const FS=`(.*?)`;',src,re.S).group(1)
def shader(kind,text):
 sh=G.glCreateShader(kind);s=C.c_char_p(text.encode());G.glShaderSource(sh,1,C.byref(s),None);G.glCompileShader(sh);ok=I();G.glGetShaderiv(sh,0x8B81,C.byref(ok))
 if not ok.value:
  buf=C.create_string_buffer(12000);G.glGetShaderInfoLog(sh,12000,None,buf);raise RuntimeError(buf.value.decode())
 return sh
pr=G.glCreateProgram();G.glAttachShader(pr,shader(0x8B31,vs));G.glAttachShader(pr,shader(0x8B30,fs));G.glLinkProgram(pr);ok=I();G.glGetProgramiv(pr,0x8B82,C.byref(ok));assert ok.value;G.glUseProgram(pr)
loc={n:G.glGetUniformLocation(pr,n.encode()) for n in ['vp','lightVP','color','eye','pick','origin','right','up','labelSize','metal','rough','alpha','selected','fade','mode','surface','hasLabel','isFloor','grid','shadowMap','labelMap']}
def u1(n,val):G.glUniform1f(loc[n],float(val))
def ui(n,val):G.glUniform1i(loc[n],int(val))
def uv(n,val):
 a=np.asarray(val,dtype=np.float32);f=G.glUniform3fv if len(a)==3 else G.glUniform2fv;f(loc[n],1,a.ctypes.data)
def um(n,val):
 a=np.ascontiguousarray(val.T,dtype=np.float32);G.glUniformMatrix4fv(loc[n],1,0,a.ctypes.data)
def unit(v):return np.array(v)/np.linalg.norm(v)
def look(e,t):
 z=unit(np.array(e)-t);x=unit(np.cross([0,0,1],z));y=np.cross(z,x);m=np.eye(4);m[:3,:3]=np.array([x,y,z]);m[:3,3]=-m[:3,:3]@np.array(e);return m
def persp(f,a,n,z):
 q=1/math.tan(f/2);return np.array([[q/a,0,0,0],[0,q,0,0],[0,0,(z+n)/(n-z),2*z*n/(n-z)],[0,0,-1,0]])
def ortho(l,r,b,t,n,f):return np.array([[2/(r-l),0,0,-(r+l)/(r-l)],[0,2/(t-b),0,-(t+b)/(t-b)],[0,0,-2/(f-n),-(f+n)/(f-n)],[0,0,0,1]])
def gen(name):
 p=U();getattr(G,name)(1,C.byref(p));return p.value
def make(arr,ref,category,mat):
 ar=np.ascontiguousarray(arr,dtype=np.float32);vao=gen('glGenVertexArrays');G.glBindVertexArray(vao);buf=gen('glGenBuffers');G.glBindBuffer(0x8892,buf);G.glBufferData(0x8892,ar.nbytes,ar.ctypes.data,0x88E4)
 for i,off in [(0,0),(1,12)]:G.glEnableVertexAttribArray(i);G.glVertexAttribPointer(i,3,0x1406,0,24,P(off))
 return {'vao':vao,'count':len(ar),'ref':ref,'category':category,'mat':mat}
D=json.loads((ROOT/'data/assembly.json').read_text());raw=np.fromfile(ROOT/'data/geometry.bin',dtype=np.float32).reshape(-1,6);items=[];decals=[]
for q in D['geometry']:items.append(make(raw[q['offset']//24:q['offset']//24+q['count']],q['ref'],q['category'],D['materials'][q['material']]))
floor=make(np.array([[-8,-8,-.004,0,0,1],[8,-8,-.004,0,0,1],[8,8,-.004,0,0,1],[-8,-8,-.004,0,0,1],[8,8,-.004,0,0,1],[-8,8,-.004,0,0,1]]),'__floor','ground',{'color':'#e5e9eb','metal':0,'rough':1})
for d in D['decals']:
 center=np.array(d['center'])/1000;r=np.array(d['right'])*d['size'][0]/2000;u=np.array(d['up'])*d['size'][1]/2000;n=unit(np.cross(d['right'],d['up']));p=[center-r-u,center+r-u,center+r+u,center-r+u];arr=np.array([np.r_[p[i],n] for i in [0,1,2,0,2,3]])
 item=make(arr,d['ref'],next(c['category'] for c in D['components'] if c['id']==d['ref']),{'color':'#ffffff','metal':0,'rough':.63});item['label']=d
 w=768;h=max(128,round(w*d['size'][1]/d['size'][0]));im=Image.new('RGBA',(w,h),d['bg']);dr=ImageDraw.Draw(im)
 for text,yy,font,cap in [(d['title'],h*.37,'DejaVuSans-Bold.ttf',.31),(d['sub'],h*.72,'DejaVuSans.ttf',.18)]:
  ff=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/'+font,max(8,int(min(h*cap,w/(len(text)*.62+2)))));dr.text((w/2,yy),text,font=ff,fill=d['ink'],anchor='mm')
 image=np.asarray(im).copy();tex=gen('glGenTextures');G.glBindTexture(0x0DE1,tex);G.glTexImage2D(0x0DE1,0,0x1908,w,h,0,0x1908,0x1401,image.ctypes.data);G.glGenerateMipmap(0x0DE1)
 for p,v in [(0x2801,0x2703),(0x2800,0x2601),(0x2802,0x812F),(0x2803,0x812F)]:G.glTexParameteri(0x0DE1,p,v)
 item['tex']=tex;decals.append(item)
shadow=gen('glGenTextures');G.glBindTexture(0x0DE1,shadow);G.glTexImage2D(0x0DE1,0,0x81A6,2048,2048,0,0x1902,0x1405,None)
for p,v in [(0x2801,0x2600),(0x2800,0x2600),(0x2802,0x812F),(0x2803,0x812F)]:G.glTexParameteri(0x0DE1,p,v)
fbo=gen('glGenFramebuffers');G.glBindFramebuffer(0x8D40,fbo);G.glFramebufferTexture2D(0x8D40,0x8D00,0x0DE1,shadow,0);G.glDrawBuffers(1,(U*1)(0));G.glReadBuffer(0);assert G.glCheckFramebufferStatus(0x8D40)==0x8CD5
light=ortho(-1.05,1.05,-1.12,1.12,.1,5)@look(np.array([-1.3,-2.1,3.4]),[0,0,.4]);um('lightVP',light);ui('shadowMap',0);ui('labelMap',1);ui('grid',1);u1('selected',0);u1('fade',0);uv('pick',[.5,.2,.1]);G.glEnable(0x0B71);G.glEnable(0x0B44);G.glCullFace(0x0405)

def draw(it,mode,deck=True):
 if it['category'] in ['accessories','covers']:return
 if not deck and it['ref'] in ['CART-DECK','DECK-MAT']:return
 if mode==2 and 'label'in it:return
 m=it['mat'];uv('color',[int(m['color'][i:i+2],16)/255 for i in [1,3,5]]);u1('metal',m.get('metal',0));u1('rough',m.get('rough',.5));u1('alpha',m.get('alpha',1));ui('surface',m.get('surface',0));ui('hasLabel',int('label'in it));ui('isFloor',int(it['ref']=='__floor'))
 if 'label'in it:
  d=it['label'];uv('origin',np.array(d['center'])/1000);uv('right',d['right']);uv('up',d['up']);uv('labelSize',np.array(d['size'])/1000);G.glActiveTexture(0x84C1);G.glBindTexture(0x0DE1,it['tex']);G.glActiveTexture(0x84C0)
 G.glBindVertexArray(it['vao']);G.glDrawArrays(4,0,it['count'])
views={'overall':(-.86,.47,2.16,[-.015,0,.46],True),'underside':(-.8,-.78,1.57,[0,0,.21],True),'power':(-.42,1.12,1.10,[-.035,0,.225],False),'controls':(-.64,1.05,.80,[-.30,0,.345],True),'drive':(-2.05,.14,.90,[-.32,-.24,.17],True)}
reports=[]
for name,(yaw,pitch,distance,target,deck)in views.items():
 eye=np.array(target)+distance*np.array([math.cos(yaw)*math.cos(pitch),math.sin(yaw)*math.cos(pitch),math.sin(pitch)]);vp=persp(37*math.pi/180,W/H,max(.001,distance/1800),20)@look(eye,target);uv('eye',eye)
 G.glActiveTexture(0x84C0);G.glBindTexture(0x0DE1,0);G.glBindFramebuffer(0x8D40,fbo);G.glViewport(0,0,2048,2048);G.glClear(0x100);um('vp',light);ui('mode',2)
 for it in items:draw(it,2,deck)
 G.glBindFramebuffer(0x8D40,0);G.glViewport(0,0,W,H);G.glClearColor(.935,.944,.95,1);G.glClear(0x4000|0x100);um('vp',vp);ui('mode',0);G.glBindTexture(0x0DE1,shadow)
 if pitch>.035:draw(floor,0,deck)
 for it in items:draw(it,0,deck)
 G.glEnable(0x8037);G.glPolygonOffset(-1,-1);G.glEnable(0x0B44)
 for it in decals:draw(it,0,deck)
 G.glEnable(0x0B44);G.glDisable(0x8037);G.glFinish();out=np.empty((H,W,4),dtype=np.uint8);G.glReadPixels(0,0,W,H,0x1908,0x1401,out.ctypes.data);error=G.glGetError();assert error==0,hex(error)
 Image.fromarray(np.flipud(out),'RGBA').convert('RGB').save(ROOT/'assets/previews'/f'render-{name}.png');reports.append({'view':name,'GL_error':error,'ground_enabled':pitch>.035,'nonuniform_pixels':int(np.count_nonzero(np.max(out[:,:,:3],axis=2)-np.min(out[:,:,:3],axis=2)>12))});print(name,flush=True)
report={'engine':G.glGetString(0x1F02).decode(),'renderer':G.glGetString(0x1F01).decode(),'scope':'Standalone EGL pbuffer executing the unmodified VS/FS strings extracted from production js/renderer.js, same geometry.bin and material data. Not a native browser WebGL test.','vertex_shader_compile':True,'fragment_shader_compile':True,'program_link':True,'depth_framebuffer_complete':True,'views':reports,'browser_webgl_test':False}
(ROOT/'docs/offscreen-render.json').write_text(json.dumps(report,indent=2))

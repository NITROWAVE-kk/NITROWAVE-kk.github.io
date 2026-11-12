import numpy as np, wave
sr=44100; T=32; n=sr*T
rs=np.random.RandomState(7)
L=np.zeros(n); Rr=np.zeros(n)
def add(buf,t,sig,g=1.0):
    i=int(t*sr); m=min(len(sig),n-i)
    if m>0: buf[i:i+m]+=sig[:m]*g
def both(t,sig,g=1.0,pan=0.0):
    add(L,t,sig,g*(1-max(pan,0))); add(Rr,t,sig,g*(1+min(pan,0)))
def tt(d): return np.arange(int(d*sr))/sr
def filt(x,lo=0,hi=1e9):
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/sr)
    X*=1/(1+(lo/np.maximum(f,1))**4); X*=1/(1+(f/hi)**4); return np.fft.irfft(X,len(x))
def midi(m): return 440*2**((m-69)/12)
def saw(f,d,nh=10):
    t=tt(d); s=np.zeros(len(t))
    for k in range(1,nh+1):
        if f*k<9000: s+=np.sin(2*np.pi*f*k*t)/k
    return s
# drums
t=tt(.32); kick=np.sin(2*np.pi*(45*t+ (110/28)*(1-np.exp(-28*t))))*np.exp(-t*11); kick[:40]*=np.linspace(0,1,40)
t=tt(.2); clap=filt(rs.randn(len(t)),900,6000)*np.exp(-t*24)*(1+.8*np.sin(2*np.pi*55*t)**8)
t=tt(.05); hat=filt(rs.randn(len(t)),7000)*np.exp(-t*90)
t=tt(.03); click=filt(rs.randn(len(t)),1500,7000)*np.exp(-t*200)
def impact(t0,g=1.0):
    t=tt(2.6); sub=np.sin(2*np.pi*(34*t+(40/5)*(1-np.exp(-5*t))))*np.exp(-t*2.2)
    cr=filt(rs.randn(len(t)),2500)*np.exp(-t*2.6)
    both(t0,sub,.9*g); add(L,t0,cr,.28*g); add(Rr,t0,np.roll(cr,300),.28*g)
def riser(t0,d,g=1.0):
    t=tt(d); u=t/d
    nz=filt(rs.randn(len(t)),1200)*u**2.5
    sw=np.sin(2*np.pi*np.cumsum(120+900*u**3)/sr)*u**2*.5
    both(t0,nz*.35+sw*.25,g)
# intro: typing + riser
for i in range(15): both(.6+i*.16,click,.5,pan=rs.uniform(-.5,.5))
t=tt(4); both(0,np.sin(2*np.pi*55*t)*np.minimum(t/2,1)*.18)
riser(1.5,2.5,.9); impact(4.0,1.0)
chords=[(57,60,64),(53,57,60),(48,52,55),(55,59,62)]  # Am F C G
side=np.ones(n)
for bar in range(12):
    t0=4+bar*2; ch=chords[bar%4]; brk=(bar==8)
    # pad
    t=tt(2.0); env=np.minimum(t/.15,1)*np.minimum((2.0-t)/.15,1)
    for j,m in enumerate(ch+(ch[0]+12,)):
        f=midi(m); s=(np.sin(2*np.pi*f*t)+.4*np.sin(2*np.pi*f*2.003*t)+.2*np.sin(2*np.pi*f*3*t))*env
        both(t0,s,.045,pan=(-.5,.5,-.2,.2)[j])
    # arp 16ths
    seq=[ch[0],ch[1],ch[2],ch[0]+12,ch[2],ch[1]+12,ch[2],ch[0]+12]*2
    for k,m in enumerate(seq):
        d=.3; t=tt(d); f=midi(m+12)
        s=(saw(f,d,6)*np.exp(-t*14)+np.sin(2*np.pi*f*t)*np.exp(-t*8))*np.minimum(t/.004,1)
        g=(.05 if brk else .085)*(1 if bar>=2 or k%2==0 else .6)
        both(t0+k*.125,s,g,pan=.6 if k%2 else -.6)
        both(t0+k*.125+.375,s,g*.35,pan=-.6 if k%2 else .6)
    if brk:
        for k in range(16): both(t0+k*.125,clap,.08+.03*k/16*4)
        for k in range(8): both(t0+1.5+k*.0625,clap,.2+.03*k)
        riser(t0,2.0,1.0); continue
    root=midi(ch[0]-24)
    for b in range(4):
        tb=t0+b*.5
        both(tb,kick,.95)
        i=int(tb*sr); m=int(.22*sr); side[i:i+m]=np.minimum(side[i:i+m],np.linspace(.15,1,m)**1.5)
        both(tb+.25,hat,.22,pan=.2)
        if bar>=4: both(tb+.125,hat,.09,pan=-.3); both(tb+.375,hat,.09,pan=-.3)
        if b%2==1: both(tb,clap,.38)
        for o in (.25,.375) if bar>=2 else (.25,):
            d=.2 if o==.25 else .11; t=tt(d)
            s=filt(saw(root*(2 if o==.375 else 1),d,12),0,900)*np.minimum(t/.005,1)*np.minimum((d-t)/.02,1)
            both(tb+o,s,.26)
# sidechain on everything except kick is approximated on the whole bus lightly
impact(22.0,1.0); impact(28.0,1.1)
# outro chord
t=tt(4.0); env=np.exp(-t*.9)*np.minimum(t/.02,1)
for j,m in enumerate((45,57,60,64,69,72)):
    f=midi(m); both(28,(np.sin(2*np.pi*f*t)+.3*np.sin(2*np.pi*f*2*t))*env,.07,pan=(0,-.4,.4,-.2,.2,0)[j])
mix=np.stack([L,Rr],1)
# simple stereo ambience
dl=int(.11*sr); amb=np.zeros_like(mix); amb[dl:,0]=mix[:-dl,1]*.12; amb[dl:,1]=mix[:-dl,0]*.12; mix+=amb
fade=np.minimum(1,(T-np.arange(n)/sr)/1.0)[:,None]; mix*=np.clip(fade,0,1)
mix=np.tanh(mix*1.5); mix*=.89/np.abs(mix).max()
w=wave.open('audio.wav','wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
w.writeframes((mix*32767).astype('<i2').tobytes()); w.close()
print('rms',np.sqrt((mix**2).mean()))

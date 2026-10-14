require('/document.js').Document.current.close();
const {Document,NewDocumentOptions,FileExportOptions,FileExportArea}=require('/document.js');
const {UnitType}=require('/units.js');
const {ShapeNodeDefinition,ImageNodeDefinition,FrameTextNodeDefinition,PolyCurveNodeDefinition,ContainerNodeDefinition}=require('/nodes.js');
const {ShapeRectangle,ShapeEllipse,ShapeCornerType}=require('/shapes.js');
const {Rectangle,Transform,TransformBuilder,PolyCurve,Curve,CurveBuilder}=require('/geometry.js');
const {RGBA8,Gradient}=require('/colours.js');
const {FillDescriptor,GradientFill,GradientFillType,BlendMode}=require('/fills.js');
const {LineStyle,LineStyleDescriptor}=require('/linestyle.js');
const {Bitmap,RasterFormat}=require('/rasterobject.js');
const {StoryBuilder}=require('/storybuilder.js');
const {GlyphAttDoubleType}=require('/glyphatts.js');
const {ParagraphAlignXType}=require('/paragraphatts.js');
const {FontFamily}=require('/fonts.js');

const DIR=require('/application.js').app.userDesktopPath+'/glow_slices/';
const o=NewDocumentOptions.createDefault();
o.units=UnitType.Pixel; o.dpi=72; o.width=1536; o.height=1024;
const doc=Document.createFromOptions(o);

const C=(h,a=255)=>RGBA8(parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16),a);
const solid=(h,a)=>FillDescriptor.createSolid(C(h,a));
const none=()=>FillDescriptor.createNone();
const stroke=w=>LineStyleDescriptor.create(LineStyle.create({weight:w}));
let target=null;
function add(def,name){ if(name) def.userDescription=name; doc.addNode(def,target); }
function group(name){ target=null; const d=ContainerNodeDefinition.createDefault(); d.userDescription=name; doc.addNode(d); target=doc.layers.first; }

function rrect(x,y,w,h,r,fill,line,sw=1,name){
  const s=ShapeRectangle.create();
  if(r>0){ s.setAbsoluteSizes(true,w,h); for(const c of [s.topLeft,s.topRight,s.bottomLeft,s.bottomRight]){ c.cornerType=ShapeCornerType.Round; c.setRadius(r,w,h);} }
  add(ShapeNodeDefinition.create(s,new Rectangle(x,y,w,h),fill?solid(fill):none(),line?solid(line):null,line?stroke(sw):null,null),name);
}
function circle(cx,cy,r,fill,line,sw=1,name){
  add(ShapeNodeDefinition.create(ShapeEllipse.create(),new Rectangle(cx-r,cy-r,2*r,2*r),fill?solid(fill):none(),line?solid(line):null,line?stroke(sw):null,null),name);
}
function path(curves,{fill,line,sw=1.5,name}={}){
  const p=PolyCurve.create(); for(const c of curves) p.addCurve(c);
  add(PolyCurveNodeDefinition.create(p,fill?solid(fill):none(),line?solid(line):none(),stroke(line?sw:0),none()),name);
}
const ln=(x1,y1,x2,y2)=>Curve.createLineXY(x1,y1,x2,y2);
const circ=(cx,cy,r)=>Curve.createEllipse(new Rectangle(cx-r,cy-r,2*r,2*r));
function poly(pts,closed){ const b=CurveBuilder.create(); b.beginXY(pts[0][0],pts[0][1]); for(const p of pts.slice(1)) b.lineToXY(p[0],p[1]); if(closed) b.close(); return b.createCurve(); }
function bez(start,segs,closed){ const b=CurveBuilder.create(); b.beginXY(start[0],start[1]); for(const s of segs) b.addBezierXY(...s); if(closed) b.close(); return b.createCurve(); }

const FONTS={};
function font(fam,t){ const k=fam+t; if(!FONTS[k]) FONTS[k]=FontFamily.all.find(f=>f.name===fam).fonts.find(f=>f.traitsName===t); return FONTS[k]; }
const SANS='Helvetica Neue', SERIF='Bodoni 72';
const ASC={'Helvetica Neue':0.73,'Bodoni 72':0.75};
// runs: string or [{t,fam,trait,color}] ; y = baseline
function text(runs,x,y,size,opt={}){
  const fam=opt.fam||SANS, w=opt.w||800, align=opt.align||'L';
  if(typeof runs==='string') runs=[{t:runs}];
  const sb=StoryBuilder.create(); sb.setToFrameTextDefaultStyle(doc.dpi,doc.format);
  if(align!=='L'){ const pa=sb.paragraphAtts; pa.alignXType=align==='C'?ParagraphAlignXType.Centre:ParagraphAlignXType.Right; sb.setParagraphAtts(pa); }
  for(const r of runs){
    const ga=sb.glyphAtts; ga.font=font(r.fam||fam,r.trait||opt.trait||(fam===SERIF?'Book':'Regular'));
    ga.setDoubleValue(GlyphAttDoubleType.Height,r.size||size);
    ga.setDoubleValue(GlyphAttDoubleType.CharacterSpacing,opt.track||0);
    ga.brushFill=solid(r.color||opt.color||'#111111'); sb.setGlyphAtts(ga); sb.addText(r.t);
  }
  const fx=align==='C'?x-w/2:(align==='R'?x-w:x);
  const def=FrameTextNodeDefinition.createFromStoryBuilder(new Rectangle(fx,y-size*(ASC[fam]||0.75),w,size*2),sb);
  if(opt.xf) def.transform=opt.xf;
  add(def,opt.name||(typeof runs[0].t==='string'?runs.map(r=>r.t).join('').slice(0,40):'Text'));
}
function image(file,x,y,name){ const im=ImageNodeDefinition.create(RasterFormat.RGBA8); im.bitmap=Bitmap.loadFromFile(DIR+file); im.transform=Transform.createTranslate(x,y); add(im,name); }

// ---- icons
function star4(cx,cy,r,fill='#111111',name='Sparkle'){
  const k=r*0.12;
  path([bez([cx,cy-r],[[cx+k,cy-k,cx+k,cy-k,cx+r,cy],[cx+k,cy+k,cx+k,cy+k,cx,cy+r],[cx-k,cy+k,cx-k,cy+k,cx-r,cy],[cx-k,cy-k,cx-k,cy-k,cx,cy-r]],true)],{fill,name});
}
function pin(cx,cy,s=1,col='#111111'){
  const r=5.5*s;
  path([bez([cx,cy+8*s],[[cx-2*s,cy+5*s,cx-r,cy+1*s,cx-r,cy-2.5*s],[cx-r,cy-6*s,cx-3*s,cy-8.5*s,cx,cy-8.5*s],[cx+3*s,cy-8.5*s,cx+r,cy-6*s,cx+r,cy-2.5*s],[cx+r,cy+1*s,cx+2*s,cy+5*s,cx,cy+8*s]],true)],{fill:col,name:'Pin'});
  circle(cx,cy-2.5*s,2.1*s,'#FFFFFF',null,1,'Pin dot');
}
function pinOutline(cx,cy,col='#222222'){
  path([bez([cx,cy+8],[[cx-2,cy+5,cx-5.5,cy+1,cx-5.5,cy-2.5],[cx-5.5,cy-6,cx-3,cy-8.5,cx,cy-8.5],[cx+3,cy-8.5,cx+5.5,cy-6,cx+5.5,cy-2.5],[cx+5.5,cy+1,cx+2,cy+5,cx,cy+8]],true),circ(cx,cy-2.5,2)],{line:col,sw:1.4,name:'Pin'});
}
const chevron=(cx,cy,col='#222222',s=1)=>path([poly([[cx-4*s,cy-2*s],[cx,cy+2*s],[cx+4*s,cy-2*s]])],{line:col,sw:1.4,name:'Chevron'});
const magnifier=(cx,cy,r,col,sw=1.5)=>path([circ(cx-r*0.15,cy-r*0.15,r),ln(cx+r*0.58,cy+r*0.58,cx+r*1.2,cy+r*1.2)],{line:col,sw,name:'Search icon'});
function heart(cx,cy,s,col,sw=1.6,fill){
  path([bez([cx,cy+0.8*s],[[cx-0.35*s,cy+0.5*s,cx-1.0*s,cy+0.05*s,cx-0.95*s,cy-0.4*s],[cx-0.9*s,cy-0.9*s,cx-0.25*s,cy-1.0*s,cx,cy-0.5*s],[cx+0.25*s,cy-1.0*s,cx+0.9*s,cy-0.9*s,cx+0.95*s,cy-0.4*s],[cx+1.0*s,cy+0.05*s,cx+0.35*s,cy+0.5*s,cx,cy+0.8*s]],true)],{line:col,sw,fill,name:'Heart icon'});
}
function shield(cx,cy,s,col){
  path([bez([cx,cy-s],[[cx+0.3*s,cy-0.8*s,cx+0.6*s,cy-0.7*s,cx+0.85*s,cy-0.7*s],[cx+0.85*s,cy-0.3*s,cx+0.85*s,cy,cx+0.85*s,cy],[cx+0.85*s,cy+0.55*s,cx+0.4*s,cy+0.9*s,cx,cy+1.05*s],[cx-0.4*s,cy+0.9*s,cx-0.85*s,cy+0.55*s,cx-0.85*s,cy],[cx-0.85*s,cy,cx-0.85*s,cy-0.3*s,cx-0.85*s,cy-0.7*s],[cx-0.6*s,cy-0.7*s,cx-0.3*s,cy-0.8*s,cx,cy-s]],true),
        poly([[cx-0.38*s,cy+0.02*s],[cx-0.08*s,cy+0.32*s],[cx+0.42*s,cy-0.25*s]])],{line:col,sw:1.6,name:'Shield icon'});
}
function calendar(cx,cy,s,col,sw=1.5){
  const w=2*s,h=1.8*s,x=cx-s,y=cy-0.8*s;
  rrect(x,y,w,h,s*0.22,null,col,sw,'Calendar body');
  path([ln(x,y+h*0.3,x+w,y+h*0.3),ln(cx-s*0.5,y-s*0.25,cx-s*0.5,y+s*0.2),ln(cx+s*0.5,y-s*0.25,cx+s*0.5,y+s*0.2)],{line:col,sw,name:'Calendar lines'});
  if(s>8) for(let r=0;r<2;r++) for(let c=0;c<3;c++) circle(cx+(c-1)*s*0.45,y+h*0.55+r*s*0.42,s*0.1,col,null,1,'dot');
}

// ================= BUILD =================
group('Background');
const grad=Gradient.create([[0,'#EEEEEE'],[0.11,'#F2F2F2'],[0.34,'#F4F4F4'],[0.5,'#F6F6F6'],[1,'#F6F6F6']].map(([p,c])=>({colour:C(c),position:p,midpoint:0.5})));
const gfd=FillDescriptor.create(GradientFill.create(grad,GradientFillType.Linear),false,Transform.createTranslate(768,0).multiply(Transform.createRotate(Math.PI/2)).multiply(Transform.createScale(894,894)),BlendMode.Normal,false);
add(ShapeNodeDefinition.create(ShapeRectangle.create(),new Rectangle(0,0,1536,1024),gfd,null,null,null),'Page background');
image('hero.png',724,0,'Hero photo (slice)');
image('dress_edge.png',712,640,'Hero dress edge (slice)');
rrect(0,893,1536,131,0,'#FAFAFA',null,1,'Brands strip');
path([ln(0,893.5,1536,893.5)],{line:'#ECECEC',sw:1,name:'Strip divider'});

group('Navigation');
text('glow',52,80,64,{fam:SERIF,w:200,name:'Logo'});
star4(162,42,7,'#111111','Logo sparkle');
const nav=[['For Clients',262],['For Providers',381],['How It Works',518],['About Us',655]];
for(const [t,x] of nav) text(t,x,69,16,{color:'#151515'});
rrect(1132,39,192,48,24,'#FFFFFF','#E6E6E6',1,'Location pill');
pin(1158,63);
text('Sydney, Australia',1175,68.5,15,{color:'#151515'});
chevron(1302,63,'#222222');
rrect(1338,38,161,50,25,'#0B0B0B',null,1,'Sign up button');
text('Sign Up / Log In',1418.5,69,16,{color:'#FFFFFF',align:'C',w:160});

group('Hero copy');
text("SYDNEY'S BEAUTY MARKETPLACE",58,202,13,{color:'#3A3A3A',track:0.3,w:500,name:'Eyebrow'});
text('Searching and booking',56,310,74,{fam:SERIF,w:900,name:'Headline line 1'});
text([{t:'for beauty '},{t:'made easier',trait:'Book Italic',size:66}],56,384,74,{fam:SERIF,w:900,name:'Headline line 2'});
star4(676,362,17,'#111111','Headline sparkle');
const para=['Glow connects you with trusted beauty retailers and','service providers across Sydney. Discover, compare','and book with ease.'];
para.forEach((t,i)=>text(t,58,443+i*30,18.5,{color:'#555555',w:620,name:'Intro line '+(i+1)}));

group('Search bar');
rrect(58,545,636,72,26,'#FFFFFF','#E9E9E9',1,'Search bar');
magnifier(90,582,7.5,'#222222',1.6);
text('Search services or treatments',113,586.5,15.5,{color:'#8A8A8A',w:240});
path([ln(347,557,347,605)],{line:'#E6E6E6',sw:1,name:'Divider'});
pinOutline(375,582);
text('Sydney, Australia',393,586.5,15,{color:'#1E1E1E',w:160});
chevron(538,581,'#222222');
rrect(569,557,113,48,18,'#0B0B0B',null,1,'Search button');
text('Search',625.5,586.5,16,{color:'#FFFFFF',align:'C',w:110});

group('Features');
const feats=[[120,'Search','Find the perfect','service'],[281,'Book','Instant booking','in seconds'],[441,'Enjoy','Feel amazing,','every time'],[599,'Trusted','Verified reviews','you can trust']];
feats.forEach(([cx,t,a,b],i)=>{
  circle(cx,700,33,'#FFFFFF','#E8E8E8',1,t+' circle');
  if(i===0) magnifier(cx+1,701,10,'#151515',1.7);
  if(i===1) calendar(cx,701,12,'#151515',1.6);
  if(i===2) heart(cx,702,13,'#151515',1.7);
  if(i===3) shield(cx,700,13,'#151515');
  text(t,cx,770,17,{align:'C',w:200,trait:'Medium',color:'#111111'});
  text(a,cx,796,14,{align:'C',w:200,color:'#6A6A6A'});
  text(b,cx,818,14,{align:'C',w:200,color:'#6A6A6A'});
  if(i<3) path([ln([201,361,520][i],700,[201,361,520][i],757)],{line:'#DDDDDD',sw:1,name:'Feature divider'});
});

group('Phone');
rrect(1071,176,323,698,52,'#2A2A2C','#9C9C9F',2,'Phone frame');
rrect(1076,181,313,688,48,'#0A0A0A',null,1,'Phone bezel');
rrect(1083,188,299,674,42,'#FFFFFF',null,1,'Screen');
rrect(1192,196,82,24,12,'#000000',null,1,'Dynamic island');
text('9:41',1116,211,13,{trait:'Medium',w:60});
[0,1,2,3].forEach(i=>rrect(1304+i*3.6,210-(i+1)*2.4,2.4,(i+1)*2.4,0.6,'#111111',null,1,'Signal'));
path([bez([1323,205],[[1326,201.5,1332,201.5,1335,205]]),bez([1325.5,207.5],[[1327.5,205.5,1330.5,205.5,1332.5,207.5]])],{line:'#111111',sw:1.4,name:'Wifi'});
circle(1329,209.5,1.2,'#111111',null,1,'Wifi dot');
rrect(1342,202,16,8.5,2.2,null,'#111111',1,'Battery');
rrect(1343.6,203.6,12.8,5.3,1.2,'#111111',null,1,'Battery level');
rrect(1358.6,204.6,1.4,3.3,0.6,'#111111',null,1,'Battery cap');
text('Welcome to Glow',1098,268,21,{fam:SERIF,w:260});
text('Your beauty, your way.',1098,288,10.5,{color:'#555555',w:200});
rrect(1098,308,230,37,10,'#FFFFFF','#ECECEC',1,'App search');
magnifier(1115,326,4.8,'#333333',1.2);
text('Search services, treatments or providers',1129,329.5,9.3,{color:'#808080',w:200});
rrect(1331,308,36,37,10,'#FFFFFF','#ECECEC',1,'Filter button');
path([ln(1342,321,1356,321),ln(1342,326.5,1356,326.5),ln(1342,332,1356,332)],{line:'#222222',sw:1.1,name:'Filter lines'});
[[1352,321],[1346,326.5],[1352,332]].forEach(([x,y])=>circle(x,y,1.8,'#FFFFFF','#222222',1.1,'Filter knob'));
text('Popular Services',1098,381,11.5,{trait:'Medium',w:200});
text('See all',1366,380.5,9.3,{color:'#555555',align:'R',w:80});
const tiles=['Facials','Nails','Brows','Hair','Makeup'];
tiles.forEach((t,i)=>{
  const x=1098+i*55.3, cx=x+24;
  rrect(x,401,48,77,10,'#F4F2F0',null,1,t+' tile');
  text(t,cx,462.5,8.5,{align:'C',w:60,color:'#333333'});
  const k='#1A1A1A';
  if(i===0){ path([circ(cx,430,8.5),bez([cx-8,425],[[cx-5,419,cx+5,419,cx+8,425]]),ln(cx-3,428.5,cx-1.5,428.5),ln(cx+1.5,428.5,cx+3,428.5),bez([cx-2,434],[[cx-1,435.5,cx+1,435.5,cx+2,434]])],{line:k,sw:1.1,name:'Facial icon'}); }
  if(i===1){ rrect(cx-5,417,10,26,4,null,k,1.1,'Finger'); rrect(cx-3,419,6,8,2.5,null,k,1.1,'Nail'); }
  if(i===2){ path([bez([cx-11,425],[[cx-4,420,cx+4,420,cx+11,425]]),bez([cx-10,433],[[cx-4,427,cx+4,427,cx+10,433]]),bez([cx-10,433],[[cx-4,439,cx+4,439,cx+10,433]]),circ(cx,433,2.8)],{line:k,sw:1.1,name:'Brow icon'}); }
  if(i===3){ path([bez([cx-9,440],[[cx-12,428,cx-9,418,cx,418],[cx+9,418,cx+12,428,cx+9,440]]),circ(cx,431,6),bez([cx-6,428],[[cx-2,423,cx+3,425,cx+6,428]])],{line:k,sw:1.1,name:'Hair icon'}); }
  if(i===4){ rrect(cx-3.5,429,7,13,1,null,k,1.1,'Lipstick base'); path([poly([[cx-2.5,429],[cx-2.5,421],[cx+2.5,418],[cx+2.5,429]],true)],{line:k,sw:1.1,name:'Lipstick tip'}); }
});
text('Top Rated in Sydney',1098,515,11.5,{trait:'Medium',w:200});
const cards=[[535,'thumb_facial.png','The Facial Room','4.9','(128)','Surry Hills','Signature Glow Facial','$149'],[656,'thumb_lash.png','Lash & Co.','4.9','(96)','Bondi Junction','Classic Lash Extensions','$129']];
for(const [y,img,name,rate,cnt,loc,svc,price] of cards){
  rrect(1097,y,270,111,10,'#FFFFFF','#EFEFEF',1,name+' card');
  image(img,1104,y+8,name+' photo (slice)');
  text(name,1195,y+22.5,11.5,{trait:'Medium',w:150});
  path([poly([...Array(10)].map((_,j)=>{const a=-Math.PI/2+j*Math.PI/5,rr=j%2?1.6:3.9;return [1199+rr*Math.cos(a),y+38+rr*Math.sin(a)];}),true)],{fill:'#111111',name:'Rating star'});
  text([{t:rate+' ',color:'#333333'},{t:cnt+'  ·  '+loc,color:'#7A7A7A'}],1205,y+41.5,8.5,{w:150});
  text(svc,1195,y+63,9,{color:'#333333',w:150});
  text(price,1195,y+92,11,{trait:'Bold',w:80});
  rrect(1306,y+77,53,23,11.5,'#0B0B0B',null,1,'Book button');
  text('Book',1332.5,y+91.8,9.5,{color:'#FFFFFF',align:'C',w:50,trait:'Medium'});
  path([poly([[1348.5,y+13],[1356.5,y+13],[1356.5,y+24],[1352.5,y+20.5],[1348.5,y+24]],true)],{line:'#222222',sw:1.1,name:'Bookmark'});
}
path([ln(1083,790,1382,790)],{line:'#F0F0F0',sw:1,name:'Tab bar divider'});
const tabs=[[1115,'Home'],[1173,'Search'],[1232,'Bookings'],[1291,'Favourites'],[1349,'Profile']];
tabs.forEach(([cx,t],i)=>{
  const col=i===0?'#111111':'#8C8C8C';
  if(i===0) path([poly([[cx-7,808],[cx,802],[cx+7,808],[cx+7,816],[cx+2,816],[cx+2,811],[cx-2,811],[cx-2,816],[cx-7,816]],true)],{fill:'#111111',name:'Home icon'});
  if(i===1) magnifier(cx,809,5.2,col,1.2);
  if(i===2) calendar(cx,809,6.5,col,1.1);
  if(i===3) heart(cx,809.5,7.2,col,1.2);
  if(i===4) path([circ(cx,805.5,3.6),bez([cx-7,816.5],[[cx-6,810.5,cx+6,810.5,cx+7,816.5]])],{line:col,sw:1.2,name:'Profile icon'});
  text(t,cx,830.5,7.8,{align:'C',w:60,color:col,trait:i===0?'Medium':'Regular'});
});
rrect(1181,851,103,4,2,'#111111',null,1,'Home indicator');

group('Trusted badge');
circle(1430,802,70,'#FFFFFF','#E4E4E4',1,'Badge');
const word='TRUSTED BY', R=47, span=1.75; // radians either side
for(let i=0;i<word.length;i++){
  if(word[i]===' ') continue;
  const th=-span/2+span*i/(word.length-1);
  const xf=new TransformBuilder().rotate(th).translateXY(1430+R*Math.sin(th),802-R*Math.cos(th)).transform;
  text(word[i],0,0,10.5,{align:'C',w:20,color:'#222222',xf,name:'Badge letter '+word[i]});
}
text('1000+',1430,808,29,{fam:SERIF,align:'C',w:140});
text('HAPPY CLIENTS',1430,827,10.5,{align:'C',w:140,track:0.1,color:'#222222'});
star4(1430,849,7,'#111111','Badge sparkle');

group('Brands');
text("TRUSTED BY SYDNEY'S LEADING BEAUTY BRANDS",768,935,12.5,{align:'C',w:800,track:0.32,color:'#333333',name:'Brands eyebrow'});
image('logos.png',100,945,'Brand logos (slice)');
target=null;
doc.saveAs(DIR+'glow_landing.af');
doc.export(DIR+'render.png',FileExportOptions.createWithPresetName('PNG'),FileExportArea.createForWholeDocument());
console.log(doc.sessionUuid);

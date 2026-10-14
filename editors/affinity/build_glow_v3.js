// Glow landing page, Affinity v3 build: "pixel-exact" mode on top of v2.
// v3 adds: every text block also as an outline traced from the original (live text kept, hidden, for editing),
// the photographed phone bezel instead of a drawn one, measured surface colours, the original 1x photos
// (the AI-enhanced 2x photos are kept as hidden alternates for 2x export), and the measured screen shape.
// Measured with tools/diffcheck.py. Inputs additionally: text_all.json (tools/text_all_spec.json manifest), hero.jpg, thumb_*.jpg.
//
// --- v2 notes ---
// Paste the whole file into the Affinity MCP execute_script tool (eval is blocked, so it can't be loaded from disk).
// Inputs live on the Desktop (Affinity can only read there): ~/Desktop/glow_slices/v2/
//   components.json  traced icons + logos (tools/slicer.py manifest, absolute design px)
//   text_paths.json  traced headline outlines (used only if the Glow Display font isn't installed)
//   tokens.json      design tokens (framework/tokens.json)
//   *_hd-2x.jpg      AI-upscaled, tone-locked photos (tools/enhance.py)
// v2 changes vs v1: traced icons instead of hand-drawn ones, the wordmark and brand logos as separate
// vector components, the headline in the custom Glow Display font, 2x photos (crisp at 2x export), Figtree body text.

const {app}=require('/application.js');
const {File}=require('/fs.js');
const {Document,NewDocumentOptions,FileExportOptions,FileExportArea}=require('/document.js');
const {UnitType}=require('/units.js');
const {ShapeNodeDefinition,ImageNodeDefinition,FrameTextNodeDefinition,PolyCurveNodeDefinition,ContainerNodeDefinition}=require('/nodes.js');
const {ShapeRectangle,ShapeEllipse,ShapeCornerType}=require('/shapes.js');
const {Selection}=require('/selections.js');
const {Rectangle,Transform,TransformBuilder,PolyCurve,Curve,CurveBuilder}=require('/geometry.js');
const {RGBA8,Gradient}=require('/colours.js');
const {FillDescriptor,GradientFill,GradientFillType,BlendMode}=require('/fills.js');
const {LineStyle,LineStyleDescriptor}=require('/linestyle.js');
const {Bitmap,RasterFormat}=require('/rasterobject.js');
const {StoryBuilder}=require('/storybuilder.js');
const {GlyphAttDoubleType}=require('/glyphatts.js');
const {ParagraphAlignXType}=require('/paragraphatts.js');
const {FontFamily}=require('/fonts.js');

const DIR=app.userDesktopPath+'/glow_slices/v2/';
const readJSON=f=>JSON.parse(File.readAll(DIR+f).toString());
const COMP={}; for(const c of readJSON('components.json')) COMP[c.name]=c;
const TOK=readJSON('tokens.json');
const col=k=>TOK.color[k].$value;

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
  const rs=Array.isArray(r)?r:[r,r,r,r]; // [topLeft, topRight, bottomRight, bottomLeft]
  if(Math.max(...rs)>0){ s.setAbsoluteSizes(true,w,h); [s.topLeft,s.topRight,s.bottomRight,s.bottomLeft].forEach((c,i)=>{ c.cornerType=ShapeCornerType.Round; c.setRadius(rs[i],w,h);}); }
  add(ShapeNodeDefinition.create(s,new Rectangle(x,y,w,h),fill?solid(fill):none(),line?solid(line):null,line?stroke(sw):null,null),name);
}
function circle(cx,cy,r,fill,line,sw=1,name){
  add(ShapeNodeDefinition.create(ShapeEllipse.create(),new Rectangle(cx-r,cy-r,2*r,2*r),fill?solid(fill):none(),line?solid(line):null,line?stroke(sw):null,null),name);
}
function line(x1,y1,x2,y2,c,name){ const p=PolyCurve.create(); p.addCurve(Curve.createLineXY(x1,y1,x2,y2)); add(PolyCurveNodeDefinition.create(p,none(),solid(c),stroke(1),none()),name); }

// traced component -> one filled vector node (potrace holes are reversed subpaths, so any fill rule works)
function traced(name,{fill,dx=0,dy=0,label}={}){
  const c=COMP[name]; if(!c){ console.log('missing component '+name); return; }
  const poly=PolyCurve.create();
  for(const sp of c.paths){
    const b=CurveBuilder.create();
    for(const s of sp){
      if(s[0]==='M') b.beginXY(s[1]+dx,s[2]+dy);
      else if(s[0]==='L') b.lineToXY(s[1]+dx,s[2]+dy);
      else if(s[0]==='C') b.addBezierXY(s[1]+dx,s[2]+dy,s[3]+dx,s[4]+dy,s[5]+dx,s[6]+dy);
      else b.close();
    }
    poly.addCurve(b.createCurve());
  }
  add(PolyCurveNodeDefinition.create(poly,solid(fill||c.colour),none(),stroke(0),none()),label||name);
}
// 2x photo placed at half scale: crisp when exported at 2x
function photo2x(file,x,y,name){ const im=ImageNodeDefinition.create(RasterFormat.RGBA8); im.bitmap=Bitmap.loadFromFile(DIR+file); im.transform=Transform.createTranslate(x,y).multiply(Transform.createScale(0.5,0.5)); add(im,name); }
function photo1x(file,x,y,name){ const im=ImageNodeDefinition.create(RasterFormat.RGBA8); im.bitmap=Bitmap.loadFromFile(DIR+file); im.transform=Transform.createTranslate(x,y); add(im,name); }
// original pixels visible; the enhanced 2x version stacked above it but hidden (show it for a crisp 2x export)
function photo(file1x,file2x,x,y,name){ photo1x(file1x,x,y,name+' (original pixels)'); photo2x(file2x,x,y,name+' (AI-enhanced 2x, hidden: show for 2x export)'); }

const fam=n=>FontFamily.all.find(f=>f.name===n);
const HAS_GLOW=!!fam('Glow Display'), HAS_FIG=!!fam('Figtree');
const SANS=HAS_FIG?'Figtree':'Helvetica Neue', SERIF='Bodoni 72', DISPLAY='Glow Display';
const FONTS={};
function font(f,t){ const k=f+t; if(!FONTS[k]){ const F=fam(f); FONTS[k]=F.fonts.find(x=>x.traitsName===t)||F.fonts[0]; } return FONTS[k]; }
const TRAIT={Regular:'Regular',Medium:HAS_FIG?'Medium':'Medium',Bold:'Bold'};
// first-baseline offset (fraction of size) for frame text, calibrated per font
// calibrated with tools/diffcheck.py (shift detection): frame top = baseline - ASC*size
const ASC={'Helvetica Neue':0.73,'Bodoni 72':0.75,'Figtree':0.735,'Glow Display':0.702};
function text(runs,x,y,size,opt={}){
  const f=opt.fam||SANS, w=opt.w||800, align=opt.align||'L';
  if(typeof runs==='string') runs=[{t:runs}];
  const sb=StoryBuilder.create(); sb.setToFrameTextDefaultStyle(doc.dpi,doc.format);
  if(align!=='L'){ const pa=sb.paragraphAtts; pa.alignXType=align==='C'?ParagraphAlignXType.Centre:ParagraphAlignXType.Right; sb.setParagraphAtts(pa); }
  for(const r of runs){
    const ga=sb.glyphAtts; const ff=r.fam||f;
    ga.font=font(ff,r.trait||opt.trait||(ff===SERIF?'Book':'Regular'));
    ga.setDoubleValue(GlyphAttDoubleType.Height,r.size||size);
    ga.setDoubleValue(GlyphAttDoubleType.CharacterSpacing,opt.track||0);
    ga.brushFill=solid(r.color||opt.color||col('ink')); sb.setGlyphAtts(ga); sb.addText(r.t);
  }
  const fx=align==='C'?x-w/2:(align==='R'?x-w:x);
  const def=FrameTextNodeDefinition.createFromStoryBuilder(new Rectangle(fx,y-size*(ASC[f]||0.75),w,size*2),sb);
  if(opt.xf) def.transform=opt.xf;
  add(def,opt.name||runs.map(r=>r.t).join('').slice(0,40));
}

// ================= BUILD =================
group('Background');
const grad=Gradient.create([[0,col('canvas-top')],[0.11,'#F2F2F2'],[0.34,'#F4F4F4'],[0.5,col('canvas')],[1,col('canvas')]].map(([p,c])=>({colour:C(c),position:p,midpoint:0.5})));
const gfd=FillDescriptor.create(GradientFill.create(grad,GradientFillType.Linear),false,Transform.createTranslate(768,0).multiply(Transform.createRotate(Math.PI/2)).multiply(Transform.createScale(894,894)),BlendMode.Normal,false);
add(ShapeNodeDefinition.create(ShapeRectangle.create(),new Rectangle(0,0,1536,1024),gfd,null,null,null),'Page background');
photo('hero.jpg','hero_hd-2x.jpg',712,0,'Hero photo');
rrect(712,50,10,26,0,'#F1F1F1',null,1,'Hero edge cleanup');
rrect(0,893,1536,131,0,'#FBFBFB',null,1,'Brands strip');
line(0,893.5,1536,893.5,'#ECECEC','Strip divider');

group('Navigation');
traced('logo_glow',{label:'Wordmark (traced)'});
traced('logo_sparkle');
for(const [t,x] of [['For Clients',262],['For Providers',381],['How It Works',518],['About Us',655]]) text(t,x,69,16,{color:'#151515'});
rrect(1132,39,192,48,24,'#F7F7F7','#E6E6E6',1,'Location pill');
traced('nav_pin',{fill:col('ink')});
text('Sydney, Australia',1175,68.5,15,{color:'#151515',track:-0.016});
traced('nav_chevron',{fill:'#222222'});
rrect(1338,38,161,50,25,'#000001',null,1,'Sign up button');
text('Sign Up / Log In',1418.5,69,16,{color:col('on-dark'),align:'C',w:160,trait:'Medium',track:-0.021});

group('Hero copy');
text("SYDNEY'S BEAUTY MARKETPLACE",58,203,13,{color:col('eyebrow'),track:0.312,w:500,name:'Eyebrow'});
if(HAS_GLOW){
  text('Searching and booking',58.5,309,73.4,{fam:DISPLAY,w:900,name:'Headline line 1 (Glow Display)'});
  text('for beauty',56.5,384,73.4,{fam:DISPLAY,w:400,name:'Headline line 2 (Glow Display)'});
  text('made easier',349.5,384,73.4,{fam:DISPLAY,trait:'Italic',w:400,name:'Headline italic (Glow Display Italic)'});
}else{
  const T={}; for(const c of readJSON('text_paths.json')) T[c.name]=c;
  for(const n of ['text_headline_1','text_headline_2_roman','text_headline_2_italic']){ COMP[n]=T[n]; traced(n,{fill:col('ink'),label:n+' (traced, install Glow Display for live text)'}); }
}
traced('h1_sparkle',{fill:col('ink')});
['Glow connects you with trusted beauty retailers and','service providers across Sydney. Discover, compare','and book with ease.'].forEach((t,i)=>text(t,58,443+i*30,18.5,{color:col('text-muted'),w:620,track:0.007,name:'Intro line '+(i+1)}));

group('Search bar');
rrect(58,545,636,72,26,'#FEFEFE','#E9E9E9',1,'Search bar');
traced('search_icon',{fill:'#222222'});
text('Search services or treatments',113,586.5,15.5,{color:col('text-faint'),w:240,track:-0.009});
line(347,557,347,605,'#E6E6E6','Divider');
traced('search_pin',{fill:'#222222'});
text('Sydney, Australia',393,586.5,15,{color:col('text'),w:160,track:-0.016});
traced('search_chevron',{fill:'#222222'});
rrect(569,557,113,48,18,'#111214',null,1,'Search button');
text('Search',625.5,586.5,16,{color:col('on-dark'),align:'C',w:110});

group('Features');
[[120,'Search','Find the perfect','service','feat_search'],[281,'Book','Instant booking','in seconds','feat_book'],[441,'Enjoy','Feel amazing,','every time','feat_enjoy'],[599,'Trusted','Verified reviews','you can trust','feat_trusted']].forEach(([cx,t,a,b,ic],i)=>{
  circle(cx,700,33,'#FBFBFB','#E8E8E8',1,t+' ring');
  traced(ic,{fill:'#151515'});
  text(t,cx,770,17,{align:'C',w:200,trait:'Medium'});
  text(a,cx,796,14,{align:'C',w:200,color:col('text-subtle')});
  text(b,cx,818,14,{align:'C',w:200,color:col('text-subtle')});
  if(i<3){ const x=[201,361,520][i]; line(x,700,x,757,col('divider'),'Feature divider'); }
});

group('Phone');
// the bezel is the photographed one in the hero slice; only the screen is drawn (measured: #F7F7F7, bottom ends at 861, bottom radius 44)
rrect(1083,188,299,673,[42,42,44,44],'#F7F7F7',null,1,'Screen');
rrect(1192,196,82,24,12,'#000000',null,1,'Dynamic island');
text('9:41',1116,211,13,{trait:HAS_FIG?'SemiBold':'Medium',w:60});
['status_bars','status_wifi','status_battery'].forEach(n=>traced(n,{fill:'#111111'}));
text('Welcome to Glow',1098,270,21.6,{fam:SERIF,w:260});
text('Your beauty, your way.',1098,288,10.5,{color:col('text-muted'),w:200});
rrect(1098,308,230,37,10,'#FEFEFE','#ECECEC',1,'App search');
traced('app_search');
text('Search services, treatments or providers',1129,329.5,9.3,{color:'#808080',w:200});
rrect(1331,308,36,37,10,'#FEFEFE','#ECECEC',1,'Filter button');
traced('app_filter');
text('Popular Services',1098,381,11.5,{trait:'Medium',w:200});
text('See all',1366,380.5,9.3,{color:col('text-muted'),align:'R',w:80});
['Facials','Nails','Brows','Hair','Makeup'].forEach((t,i)=>{
  const x=1098+i*55.3;
  rrect(x,401,48,77,10,'#EFEDEB',null,1,t+' tile');
  traced('tile_'+t.toLowerCase());
  text(t,x+24,462.5,8.5,{align:'C',w:60,color:'#333333'});
});
text('Top Rated in Sydney',1098,515,11.5,{trait:'Medium',w:200});
[[535,'thumb_facial.jpg','thumb_facial_hd-2x.jpg','The Facial Room','4.9','(128)','Surry Hills','Signature Glow Facial','$149'],[656,'thumb_lash.jpg','thumb_lash_hd-2x.jpg','Lash & Co.','4.9','(96)','Bondi Junction','Classic Lash Extensions','$129']].forEach(([y,img1,img,name,rate,cnt,loc,svc,price],i)=>{
  rrect(1097,y,270,111,10,'#FCFCFB',col('line-soft'),1,name+' card');
  photo(img1,img,1104,y+8,name+' photo');
  text(name,1195,y+22.5,11.5,{trait:'Medium',w:150});
  traced('card_star',{dy:y-535,label:'Rating star'});
  text([{t:rate+' ',color:'#333333'},{t:cnt+'  ·  '+loc,color:'#7A7A7A'}],1205,y+41.5,8.5,{w:150});
  text(svc,1195,y+63,9,{color:'#333333',w:150});
  text(price,1195,y+92,11,{trait:'Bold',w:80});
  rrect(1307,y+77,52,23,11.5,'#060606',null,1,'Book button');
  text('Book',1332.5,y+91.8,9.5,{color:col('on-dark'),align:'C',w:50,trait:'Medium'});
  traced('card_bookmark',{dy:y-535,label:'Bookmark'});
});
line(1083,790,1382,790,'#F0F0F0','Tab bar divider');
[['home','Home',1115],['search','Search',1173],['bookings','Bookings',1232],['favourites','Favourites',1291],['profile','Profile',1349]].forEach(([n,t,cx],i)=>{
  traced('tab_'+n);
  text(t,cx,830.5,7.8,{align:'C',w:60,color:i===0?col('ink'):'#8C8C8C',trait:i===0?'Medium':'Regular'});
});
rrect(1181,851,103,4,2,col('ink'),null,1,'Home indicator');

group('Trusted badge');
circle(1430,802,70,'#FEFEFE','#E4E4E4',1,'Badge');
const word='TRUSTED BY', R=47, span=1.75;
for(let i=0;i<word.length;i++){
  if(word[i]===' ') continue;
  const th=-span/2+span*i/(word.length-1);
  const xf=new TransformBuilder().rotate(th).translateXY(1430+R*Math.sin(th),802-R*Math.cos(th)).transform;
  text(word[i],0,0,10.5,{align:'C',w:20,color:'#222222',xf,name:'Badge letter '+word[i]});
}
if(HAS_GLOW) text('1000+',1430,807,25,{fam:DISPLAY,align:'C',w:140,name:'1000+ (Glow Display)'}); else text('1000+',1430,808,29,{fam:SERIF,align:'C',w:140});
text('HAPPY CLIENTS',1430,827,10.5,{align:'C',w:140,track:0.1,color:'#222222'});
traced('badge_sparkle');

group('Brands');
text("TRUSTED BY SYDNEY'S LEADING BEAUTY BRANDS",768,935,12.5,{align:'C',w:800,track:0.292,color:'#333333',name:'Brands eyebrow'});
for(const n of ['logo_mecca','logo_adorebeauty','logo_benefit','logo_endota','logo_sephora','logo_elleebana','logo_kevinmurphy']){
  group('Logo: '+n.slice(5)); traced(n);
}
target=null;

// pixel-exact text: every text block traced from the original, on top; the live text above is hidden (not deleted)
group('Pixel-exact text (traced from original)');
for(const c of readJSON('text_all.json')){ COMP[c.name]=c; traced(c.name,{label:c.name.replace(/^tx_/,'')}); }
target=null;
// hide the live text frames and the enhanced-photo alternates (kept for editing / 2x export).
// Found by walking the tree: inside a group, the node just added is NOT children.first, so don't track it from add().
const ALL=[], HIDE=[];
(function walk(c){ for(const n of c){ ALL.push(n); if(n.children) walk(n.children); } })(doc.layers);
for(const n of ALL){ const d=(n.descriptionInterface&&n.descriptionInterface.userDescription)||''; if(n.isFrameTextNode||d.indexOf('AI-enhanced 2x')>=0) HIDE.push(n); }
doc.setVisible(true, Selection.create(doc, ALL));
doc.setVisible(false, Selection.create(doc, HIDE));

doc.saveAs(DIR+'glow_landing_v3.af');
doc.export(DIR+'glow_landing_v3.png',FileExportOptions.createWithPresetName('PNG'),FileExportArea.createForWholeDocument());
console.log(doc.sessionUuid+' hidden='+HIDE.length);

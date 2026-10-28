#include "/Users/chingun/Downloads/glow-site/editors/photoshop/lib.jsx"
// Fluttering Penguins in Photoshop: the kit (tools/recreate.py penguins kit photoshop --out ~/Downloads/penguins_kit)
// placed as layers, live text (Pretendard, hidden), the exact-mode group on top; exports standard / max / exact
// renders and saves penguins_ps.psd. Run with: osascript -e 'tell application "Adobe Photoshop 2026" to do javascript (read POSIX file "<this file>")'
app.preferences.typeUnits=TypeUnits.PIXELS;
while(app.documents.length) app.documents[0].close(SaveOptions.DONOTSAVECHANGES);
var K=Folder("~/Downloads/penguins_kit").fsName+"/", D=Folder("~/Downloads/penguins_photoshop").fsName+"/";
var doc=app.documents.add(1214,1295,72,"penguins_ps",NewDocumentMode.RGB,DocumentFill.WHITE,1,BitsPerChannelType.EIGHT,"sRGB IEC61966-2.1");
var bg=doc.layers[0]; var out=[];
out.push(placeAt(K+"backdrop_plate.png","Background plate (photos cleaned with content-aware fill)",0,0));
bg.isBackgroundLayer=false; bg.remove();
out.push(placeAt(K+"hero_outline_button_backdrop.png","Outline button (fitted fill, ring and shadow: tools/fit_pill.py)",0,0));
out.push(placeAt(K+"shapes_tuned.svg","Shapes (tuned: buttons, icon circles, dividers)",0,0));
out.push(placeAt(K+"vectors_tuned.svg","Tuned vectors (logo, icons, headings)",0,0));
out.push(placeAt(K+"vectors_tiny_hidden.svg","Small text (vectors, hidden: use for 2x)",0,0)); doc.activeLayer.visible=false;
out.push(placeAt(K+"cutouts_tiny.png","Small text (original pixels)",0,0));
out.push(placeAt(K+"cutouts_all_max_fidelity.png","Max fidelity: all elements as original pixels",0,0)); doc.activeLayer.visible=false;
// live text
doc.activeLayer=doc.layers[0];
var g=doc.layerSets.add(); g.name="Live text (editable, Pretendard)";
function mk(name,str,font,size,x,y,hex){
  var l=g.artLayers.add(); l.kind=LayerKind.TEXT; l.name=name;
  var t=l.textItem; t.contents=str; try{t.font=font;}catch(e){} t.size=size;
  var c=new SolidColor(); c.rgb.hexValue=hex; t.color=c; t.antiAliasMethod=AntiAlias.SMOOTH; t.position=[x,y];
}
#include "/Users/chingun/Downloads/glow-site/projects/penguins/editors/photoshop/live_text.jsx"
g.visible=false;
function exp(n){var o=new ExportOptionsSaveForWeb(); o.format=SaveDocumentType.PNG; o.PNG8=false; o.transparency=false; o.interlaced=false; o.includeProfile=false; o.optimized=true; doc.exportDocument(new File(D+n),ExportType.SAVEFORWEB,o);}
function L(n){return doc.layers.getByName(n);}
var maxL=L("Max fidelity: all elements as original pixels"), vec=L("Tuned vectors (logo, icons, headings)"), tiny=L("Small text (original pixels)"), tinyV=L("Small text (vectors, hidden: use for 2x)");
maxL.visible=true; vec.visible=false; tiny.visible=false; exp("penguins_ps_max.png");
maxL.visible=false; tinyV.visible=true; tiny.visible=false; vec.visible=true; exp("penguins_ps_vectors_only.png");
tinyV.visible=false; tiny.visible=true; exp("penguins_ps.png");
// exact group on top
var f=new File(K+"exact/layers.json"); f.open("r"); var EL=eval("("+f.read()+")"); f.close();
var top=doc.layers[0]; var set=doc.layerSets.add(); set.name="Exact: original decomposed into layers (hide to see the rebuild)";
set.move(top,ElementPlacement.PLACEBEFORE);
for(var i=EL.length-1;i>=0;i--){ placeAt(K+"exact/"+EL[i].file,EL[i].name,0,0); var l=doc.activeLayer; l.rasterize(RasterizeType.ENTIRELAYER); l.move(set,ElementPlacement.PLACEATEND); }
exp("penguins_ps_exact.png");
var so=new PhotoshopSaveOptions(); so.embedColorProfile=true; so.layers=true; so.maximizeCompatibility=true;
doc.saveAs(new File(D+"penguins_ps.psd"),so,false);
out.join("\n");

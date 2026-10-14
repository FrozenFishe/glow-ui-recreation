#include "lib.jsx"
app.preferences.typeUnits=TypeUnits.PIXELS;
var doc=app.activeDocument; var out=[];
doc.activeLayer=doc.layers[0];
var g=doc.layerSets.add(); g.name="Live text (editable)";
function mk(name,str,font,size,x,y,hex){
  var l=g.artLayers.add(); l.kind=LayerKind.TEXT; l.name=name;
  var t=l.textItem; t.contents=str; t.font=font; t.size=size;
  var c=new SolidColor(); c.rgb.hexValue=hex; t.color=c; t.antiAliasMethod=AntiAlias.SMOOTH;
  t.position=[x,y];
  out.push(name+" font="+t.font+" size="+t.size+" pos="+t.position+" bounds="+b(l));
}
var lines=["Glow connects you with trusted beauty retailers and","service providers across Sydney. Discover, compare","and book with ease."];
for(var i=lines.length-1;i>=0;i--) mk("Intro line "+(i+1),lines[i],"Figtree-Regular",18.5,58,443+i*30,"555555");
mk("Headline line 1","Searching and booking","GlowDisplay-Regular",73.4,58.5,309,"0D0D0D");
g.visible=false;
out.join("\n");

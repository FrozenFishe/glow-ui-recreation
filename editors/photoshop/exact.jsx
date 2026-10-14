#include "lib.jsx"
// Exact mode: add the original decomposed into named layers (tools/exact_layers.py -> <kit>/exact/) as a group on top
// of the rebuild, export it, and save glow_ps_v9.psd. Run build_v7.jsx (+ export_v7.jsx) first, with the kit built by
// make_kit.py --calibration tools/calibration_photoshop.json --photo-edges 2 (v9; the v8 PSD used the v7 kit).
// The group composites back to the original bit for bit; hide it to see the redrawn (vector) version underneath.
var doc=app.activeDocument; var K=Folder("~/Downloads/glow_v5_kit/exact").fsName+"/"; var D=Folder("~/Downloads/glow_photoshop").fsName+"/";
var f=new File(K+"layers.json"); f.open("r"); var L=eval("("+f.read()+")"); f.close();
var top=doc.layers[0];
var set=doc.layerSets.add(); set.name="Exact: original decomposed into layers (hide to see the rebuild)";
set.move(top,ElementPlacement.PLACEBEFORE);
var out=[];
for(var i=L.length-1;i>=0;i--){  // top to bottom, each appended below the previous
  out.push(placeAt(K+L[i].file,L[i].name,0,0));
  var l=doc.activeLayer; l.rasterize(RasterizeType.ENTIRELAYER); l.move(set,ElementPlacement.PLACEATEND);
}
function exp(n){var o=new ExportOptionsSaveForWeb(); o.format=SaveDocumentType.PNG; o.PNG8=false; o.transparency=false; o.interlaced=false; o.includeProfile=false; o.optimized=true; doc.exportDocument(new File(D+n),ExportType.SAVEFORWEB,o);}
exp("glow_ps_exact.png");
var so=new PhotoshopSaveOptions(); so.embedColorProfile=true; so.layers=true; so.maximizeCompatibility=true;
doc.saveAs(new File(D+"glow_ps_v9.psd"),so,false);
out.join("\n");

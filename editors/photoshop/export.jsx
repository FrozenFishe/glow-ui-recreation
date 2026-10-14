#include "lib.jsx"
var doc=app.activeDocument; var D="~/Downloads/glow_photoshop/";
function L(n){return doc.layers.getByName(n);}
function exp(f){var o=new ExportOptionsSaveForWeb(); o.format=SaveDocumentType.PNG; o.PNG8=false; o.transparency=false; o.interlaced=false; o.includeProfile=false; o.optimized=true;
 doc.exportDocument(new File(D+f),ExportType.SAVEFORWEB,o);}
var maxL=L("Max fidelity: all elements as original pixels"), vec=L("Tuned vectors"), tiny=L("Tiny elements (original pixels)");
// max variant
maxL.visible=true; vec.visible=false; tiny.visible=false; exp("glow_ps_v5_max.png");
// standard variant
maxL.visible=false; vec.visible=true; tiny.visible=true; exp("glow_ps_v5.png");
var so=new PhotoshopSaveOptions(); so.embedColorProfile=true; so.layers=true; so.maximizeCompatibility=true;
doc.saveAs(new File(D+"glow_ps_v5.psd"),so,false);
"ok "+doc.fullName;

#include "lib.jsx"
// Photoshop v6: v5 kit + strip edge (original rows 892-895) instead of a drawn divider line
while(app.documents.length) app.documents[0].close(SaveOptions.DONOTSAVECHANGES);
var K="~/Downloads/glow_v5_kit/";
var doc=app.documents.add(1536,1024,72,"glow_ps_v6",NewDocumentMode.RGB,DocumentFill.WHITE,1,BitsPerChannelType.EIGHT,"sRGB IEC61966-2.1");
var bg=doc.layers[0];
var out=[];
out.push(placeAt(K+"backdrop.png","Backdrop",0,0));
bg.isBackgroundLayer=false; bg.remove();
out.push(placeAt(K+"hero_exact.png","Hero photo (original pixels)",712,0));
out.push(placeAt(K+"strip_edge.png","Strip edge (original pixels)",0,892));
out.push(placeAt(K+"shapes_tuned.svg","Shapes (tuned)",0,0));
out.push(placeAt(K+"thumb_facial_exact.png","Card photo 1",1104,543));
out.push(placeAt(K+"thumb_lash_exact.png","Card photo 2",1104,664));
out.push(placeAt(K+"vectors_tuned.svg","Tuned vectors",0,0));
out.push(placeAt(K+"vectors_tiny_hidden.svg","Tiny elements (vectors, hidden: use for 2x)",0,0));
doc.activeLayer.visible=false;
out.push(placeAt(K+"cutouts_tiny.png","Tiny elements (original pixels)",0,0));
out.push(placeAt(K+"cutouts_all_max_fidelity.png","Max fidelity: all elements as original pixels",0,0));
doc.activeLayer.visible=false;
out.join("\n");

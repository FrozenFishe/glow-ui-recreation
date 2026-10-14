app.preferences.rulerUnits = Units.PIXELS;
app.displayDialogs = DialogModes.NO;
function placeFile(path){
  var d = new ActionDescriptor();
  d.putPath(charIDToTypeID("null"), new File(path));
  d.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
  var o = new ActionDescriptor();
  o.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), 0);
  o.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), 0);
  d.putObject(charIDToTypeID("Ofst"), charIDToTypeID("Ofst"), o);
  executeAction(charIDToTypeID("Plc "), d, DialogModes.NO);
  return app.activeDocument.activeLayer;
}
function b(l){var x=l.bounds;return [x[0].as("px"),x[1].as("px"),x[2].as("px"),x[3].as("px")];}
function moveTo(l,x,y){var q=b(l);l.translate(x-q[0],y-q[1]);return b(l);}
function soInfo(){
  var ref=new ActionReference(); ref.putEnumerated(charIDToTypeID("Lyr "),charIDToTypeID("Ordn"),charIDToTypeID("Trgt"));
  var d=executeActionGet(ref); var so=d.getObjectValue(stringIDToTypeID("smartObjectMore"));
  var s=so.getObjectValue(stringIDToTypeID("size")); var t=so.getList(stringIDToTypeID("transform")); var tr=[];
  for(var i=0;i<t.count;i++)tr.push(t.getDouble(i));
  return {w:s.getDouble(stringIDToTypeID("width")),h:s.getDouble(stringIDToTypeID("height")),tr:tr};
}
function placeAt(path,name,x,y){
  var l=placeFile(path); l.name=name;
  var i=soInfo(); var dx=x-i.tr[0], dy=y-i.tr[1];
  if(dx!=0||dy!=0) l.translate(dx,dy);
  i=soInfo();
  return name+": size "+i.w+"x"+i.h+" topleft "+i.tr[0]+","+i.tr[1]+" botright "+i.tr[4]+","+i.tr[5]+" bounds "+b(l);
}

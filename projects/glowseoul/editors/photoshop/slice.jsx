// GlowSeoul: clean the hero plate (content-aware fill under the UI mask), add named user slices, export each slice.
app.preferences.rulerUnits = Units.PIXELS;
app.displayDialogs = DialogModes.NO;
var ROOT = "~/Downloads/glow-site/projects/glowseoul/"; // ExtendScript expands ~; change if the repo lives elsewhere
function c(s){return charIDToTypeID(s);} function s(x){return stringIDToTypeID(x);}
var SLICES = [
  ["hero", 0, 0, 1672, 815],
  ["thumb_toners", 100, 844, 73, 72], ["thumb_serums", 374, 846, 68, 69], ["thumb_moisturisers", 643, 846, 77, 70],
  ["thumb_sunscreens", 897, 845, 75, 71], ["thumb_masks", 1146, 847, 62, 68], ["thumb_cleansers", 1385, 843, 78, 77],
  ["flag_au", 366, 176, 30, 26]
];
var doc = app.open(new File(ROOT + "design.png"));
if (doc.mode != DocumentMode.RGB) doc.changeMode(ChangeMode.RGB);
doc.activeLayer.isBackgroundLayer = false; doc.activeLayer.name = "Original";
var clean = doc.activeLayer.duplicate(); clean.name = "Hero clean (content-aware fill)";
doc.activeLayer = clean;
// mask -> selection
var m = app.open(new File(ROOT + "build/ui_mask.png"));
m.selection.selectAll(); m.selection.copy(); m.close(SaveOptions.DONOTSAVECHANGES);
app.activeDocument = doc;
var ch = doc.channels.add(); ch.name = "UI mask"; doc.activeChannels = [ch]; doc.paste();
doc.selection.load(ch); doc.activeChannels = doc.componentChannels; doc.activeLayer = clean;
var d = new ActionDescriptor();
d.putEnumerated(c("Usng"), c("FlCn"), s("contentAware"));
d.putBoolean(s("contentAwareColorAdaptationFill"), true);
d.putUnitDouble(c("Opct"), c("#Prc"), 100); d.putEnumerated(c("Md  "), c("BlnM"), c("Nrml"));
executeAction(c("Fl  "), d, DialogModes.NO);
doc.selection.deselect();
// thumbnails/flag come from the original
// export each slice: crop -> Save for Web PNG-24 -> back in history
var o = new ExportOptionsSaveForWeb(); o.format = SaveDocumentType.PNG; o.PNG8 = false; o.transparency = false; o.includeProfile = false;
var out = [];
for (var i = 0; i < SLICES.length; i++) {
  var z = SLICES[i]; var st = doc.activeHistoryState;
  clean.visible = (z[0] == "hero");
  doc.crop([z[1], z[2], z[1] + z[3], z[2] + z[4]]);
  doc.exportDocument(new File(ROOT + "slices/photoshop/" + z[0] + ".png"), ExportType.SAVEFORWEB, o);
  doc.activeHistoryState = st; out.push(z[0]);
}
clean.visible = true;
doc.exportDocument(new File(ROOT + "build/ps_clean_full.png"), ExportType.SAVEFORWEB, o);
// user slices (kept in the PSD)
for (var i = 0; i < SLICES.length; i++) {
  var z = SLICES[i];
  var desc = new ActionDescriptor(), ref = new ActionReference(); ref.putClass(s("slice"));
  desc.putReference(c("null"), ref);
  var sl = new ActionDescriptor(); sl.putEnumerated(s("type"), s("sliceType"), s("user"));
  var r = new ActionDescriptor();
  r.putUnitDouble(c("Top "), c("#Pxl"), z[2]); r.putUnitDouble(c("Left"), c("#Pxl"), z[1]);
  r.putUnitDouble(c("Btom"), c("#Pxl"), z[2] + z[4]); r.putUnitDouble(c("Rght"), c("#Pxl"), z[1] + z[3]);
  sl.putObject(c("At  "), c("Rctn"), r); desc.putObject(c("Usng"), s("slice"), sl);
  try { executeAction(c("Mk  "), desc, DialogModes.NO); } catch (e) {}
}
doc.saveAs(new File(ROOT + "editors/photoshop/glowseoul_slices.psd"), new PhotoshopSaveOptions(), true);
"ok " + out.join(",");

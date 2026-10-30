// Google Apps Script: keeps a copy of Oracle's Elixir's newest CSV in YOUR OWN Drive folder.
// Google limits downloads of their original file; a copy in your folder has no such limit.
const SOURCE_FOLDER_ID = '1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH';   // Oracle's Elixir public folder
const DEST_FOLDER_ID   = 'PASTE_YOUR_FOLDER_ID_HERE';            // your folder (shared: anyone with the link can view)
const FILE_NAME        = '2026_LoL_esports_match_data_from_OraclesElixir.csv';

function copyLatest() {
  const src = DriveApp.getFolderById(SOURCE_FOLDER_ID).getFilesByName(FILE_NAME);
  if (!src.hasNext()) throw new Error('Source file not found');
  const file = src.next();
  const dest = DriveApp.getFolderById(DEST_FOLDER_ID);
  const old = [];
  const it = dest.getFilesByName(FILE_NAME);
  while (it.hasNext()) old.push(it.next());
  if (old.length && old[0].getLastUpdated() >= file.getLastUpdated()) return;   // copy is already current
  file.makeCopy(FILE_NAME, dest);
  old.forEach(function (f) { f.setTrashed(true); });
}

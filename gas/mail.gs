/**
 * 天気図配信のメール送信とアーカイブ(Google Apps Script)。
 * GitHub Actions が公開したページ(latest.json・画像・latest.pdf)を取ってきて、
 *   1) Google ドライブの「天気図アーカイブ/年/月」に画像とPDFを保存する
 *   2) 自分宛てに画像添付でメールを送る
 * アプリパスワード不要。setup() で作るトリガーが10分ごとにページを見て、新しい回が公開されていたら動く。
 * 同じ回を2度送らないよう、送った画像名を覚えておく。
 */
const PAGE = 'https://naokishobosai0214-dot.github.io/tenkizu-haishin/';
const TO = 'nao.kishobosai.0214@gmail.com';
const ARCHIVE = '天気図アーカイブ';

function sendCharts() {
  const pages = JSON.parse(UrlFetchApp.fetch(PAGE + 'latest.json?t=' + Date.now()).getContentText());
  const key = pages.map(p => p.full).join(',');
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('last') === key) return;  // まだ新しい回が公開されていない
  const now = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'MM/dd HH:mm');
  const files = pages.map(p => UrlFetchApp.fetch(PAGE + p.full).getBlob().setName(p.full));
  saveArchive(pages, files);
  const body = '天気図 ' + now + '\n\n' + pages.map(p => '・' + p.title).join('\n') +
    '\n\nページで見る: ' + PAGE + '\nアーカイブ: ' + archiveRoot().getUrl() + '\n\n出典：気象庁ホームページ';
  MailApp.sendEmail({to: TO, subject: '天気図 ' + now, body: body, attachments: files});
  props.setProperty('last', key);
}

// 「天気図アーカイブ」フォルダ(なければ作る)
function archiveRoot() {
  const it = DriveApp.getFoldersByName(ARCHIVE);
  return it.hasNext() ? it.next() : DriveApp.createFolder(ARCHIVE);
}

function subFolder(parent, name) {
  const it = parent.getFoldersByName(name);
  return it.hasNext() ? it.next() : parent.createFolder(name);
}

// 天気図アーカイブ/2026/10/ に「20261011_0356UTC_1_地上天気図.jpg」「20261011_0356UTC_天気図.pdf」の形で保存する
function saveArchive(pages, files) {
  const t = new Date();
  const stamp = Utilities.formatDate(t, 'UTC', "yyyyMMdd_HHmm'UTC'");
  const month = subFolder(subFolder(archiveRoot(), Utilities.formatDate(t, 'UTC', 'yyyy')), Utilities.formatDate(t, 'UTC', 'MM'));
  pages.forEach((p, i) => {
    const name = stamp + '_' + (i + 1) + '_' + p.title.replace(/[\\/:*?"<>|]/g, '') + '.jpg';
    month.createFile(files[i].copyBlob().setName(name));
  });
  const pdf = UrlFetchApp.fetch(PAGE + 'latest.pdf?t=' + Date.now()).getBlob().setName(stamp + '_天気図.pdf');
  month.createFile(pdf);
}

// 最初に1回だけ実行: 10分ごとに sendCharts を動かすトリガーを作る(新しい回がなければ何もしない)
// あわせてアーカイブのフォルダを作り、URLを実行ログに出す(リッチメニューに使う)
function setup() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('sendCharts').timeBased().everyMinutes(10).create();
  Logger.log(archiveRoot().getUrl());
}

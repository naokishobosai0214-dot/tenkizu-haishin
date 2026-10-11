/**
 * 天気図配信のメール送信(Google Apps Script)。
 * GitHub Actions が公開したページ(latest.json と画像)を取ってきて、自分宛てに画像添付で送る。
 * アプリパスワード不要。時刻は setup() で作るトリガー(毎日7時台・19時台)。
 * 同じ回を2度送らないよう、送った画像名を覚えておく。
 */
const PAGE = 'https://naokishobosai0214-dot.github.io/tenkizu-haishin/';
const TO = 'nao.kishobosai.0214@gmail.com';

function sendCharts() {
  const pages = JSON.parse(UrlFetchApp.fetch(PAGE + 'latest.json?t=' + Date.now()).getContentText());
  const key = pages.map(p => p.full).join(',');
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('last') === key) return;  // まだ新しい回が公開されていない
  const now = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'MM/dd HH:mm');
  const files = pages.map(p => UrlFetchApp.fetch(PAGE + p.full).getBlob().setName(p.full));
  const body = '天気図 ' + now + '\n\n' + pages.map(p => '・' + p.title).join('\n') +
    '\n\nページで見る: ' + PAGE + '\n\n出典：気象庁ホームページ';
  MailApp.sendEmail({to: TO, subject: '天気図 ' + now, body: body, attachments: files});
  props.setProperty('last', key);
}

// 最初に1回だけ実行: 毎日7時台と19時台に sendCharts を動かすトリガーを作る
function setup() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  [7, 19].forEach(h => ScriptApp.newTrigger('sendCharts').timeBased().everyDays(1).atHour(h).nearMinute(15).inTimezone('Asia/Tokyo').create());
}

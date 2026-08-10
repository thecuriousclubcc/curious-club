import type { Theme } from './themes'

// Both languages ship from day one. Retrofitting bilingual copy across five
// screens later costs more than writing the second column now.

export type Locale = 'ja' | 'en'

export const LOCALES: Locale[] = ['ja', 'en']

type Dict = Record<string, string>

const en: Dict = {
  'tab.now': 'NOW',
  'tab.in': 'IN',
  'tab.day': 'DAY',
  'tab.all': 'ALL',
  'tab.me': 'ME',

  'now.start': 'Start dirty',
  'now.startHint': '5 minutes, allowed to be bad',
  'now.notNow': 'Not now',
  'now.nope': 'Nope',
  'now.done': 'Done',
  'now.firstStepPrompt': "What's the first move?",
  'now.firstStepHelp': 'Something physical. Two minutes or less.',
  'now.firstStepSave': 'Save it',
  'now.firstStepPlaceholder': 'open the editor / find the receipt',
  'now.deadline': 'due',
  'now.stop': 'Stop',
  'now.timeLeft': 'left',

  'capture.placeholder': 'Anything. No fields.',
  'capture.add': 'Add',
  'capture.voice': 'Speak',
  'capture.listening': 'Listening…',
  'capture.saved': 'In.',

  'in.title': 'Inbox',
  'in.amnesty': 'Amnesty',
  'in.amnestyHint': 'Clears the inbox. No questions, no counter.',
  'in.promote': 'Take it on',

  'day.deadlines': 'Hard deadlines',
  'day.none': 'Nothing externally imposed.',
  'day.finished': 'Finished today',

  'all.title': 'Everything',
  'all.mode.list': 'List',
  'all.mode.deck': 'Deck',
  'all.mode.roulette': 'Roulette',
  'all.spin': 'Pick one for me',
  'all.cold': 'Gone quiet',
  'all.coldPrompt': 'Still want this?',
  'all.keep': 'Keep',
  'all.letGo': 'Let go',
  'all.next': 'Next',

  'me.streak': 'Done in the last 7 days',
  'me.streakNote': 'This number never resets to zero.',
  'me.log': 'Done log',
  'me.theme': 'Theme',
  'me.themePinned': 'Pinned',
  'me.pin': 'Keep this one',
  'me.unpin': 'Resume rotation',
  'me.shuffle': 'Shuffle now',
  'me.rotationNote': 'Changes by itself every 3 days, at 4am.',
  'me.language': 'Language',
  'me.install': 'Add to home screen from your browser menu.',
  'me.daysLeft': 'Changes in {n} days',
  'me.dayLeft': 'Changes tomorrow',

  'reveal.new': 'New look',
  'empty.now': 'Nothing waiting.',
  'empty.in': 'Inbox empty.',
  'empty.all': 'Nothing here yet.',
  'empty.log': 'Nothing logged yet.',
}

const ja: Dict = {
  'tab.now': 'いま',
  'tab.in': '受信',
  'tab.day': '今日',
  'tab.all': '全部',
  'tab.me': '自分',

  'now.start': 'とりあえず始める',
  'now.startHint': '5分だけ。下手でいい',
  'now.notNow': '今はやらない',
  'now.nope': 'やらない',
  'now.done': 'できた',
  'now.firstStepPrompt': '最初の一手は？',
  'now.firstStepHelp': '体が動かせること。2分以内で。',
  'now.firstStepSave': '保存',
  'now.firstStepPlaceholder': '編集ソフトを開く / レシートを探す',
  'now.deadline': '期限',
  'now.stop': 'やめる',
  'now.timeLeft': '残り',

  'capture.placeholder': 'なんでも。入力欄はこれだけ。',
  'capture.add': '追加',
  'capture.voice': '話す',
  'capture.listening': '聞いています…',
  'capture.saved': '入れました。',

  'in.title': '受信箱',
  'in.amnesty': '全部なかったことにする',
  'in.amnestyHint': '受信箱を空にします。確認も件数表示もしません。',
  'in.promote': 'やると決める',

  'day.deadlines': '外から決められた期限',
  'day.none': '外から決められたものはありません。',
  'day.finished': '今日できたこと',

  'all.title': '全部',
  'all.mode.list': 'リスト',
  'all.mode.deck': 'カード',
  'all.mode.roulette': 'ルーレット',
  'all.spin': 'ひとつ選んで',
  'all.cold': '静かになったもの',
  'all.coldPrompt': 'まだやりたい？',
  'all.keep': '残す',
  'all.letGo': '手放す',
  'all.next': '次',

  'me.streak': '直近7日でできたこと',
  'me.streakNote': 'この数字はゼロに戻りません。',
  'me.log': '記録',
  'me.theme': '見た目',
  'me.themePinned': '固定中',
  'me.pin': 'これのままにする',
  'me.unpin': '自動で変える',
  'me.shuffle': '今すぐ変える',
  'me.rotationNote': '3日ごと、朝4時に自動で変わります。',
  'me.language': '言語',
  'me.install': 'ブラウザのメニューからホーム画面に追加してください。',
  'me.daysLeft': 'あと{n}日で変わります',
  'me.dayLeft': '明日変わります',

  'reveal.new': '新しい見た目',
  'empty.now': '待っているものはありません。',
  'empty.in': '受信箱は空です。',
  'empty.all': 'まだ何もありません。',
  'empty.log': 'まだ記録はありません。',
}

const DICTS: Record<Locale, Dict> = { ja, en }

export function t(locale: Locale, key: string): string {
  return DICTS[locale][key] ?? DICTS.en[key] ?? key
}

/**
 * Interpolating `{n}` rather than concatenating around a number, because
 * Japanese takes no space between the count and its counter and English does.
 */
export function tf(locale: Locale, key: string, vars: Record<string, string | number>): string {
  return t(locale, key).replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? ''))
}

/** Empty-state lines, drawn from the pool the active theme's voice points at. */
const VOICE_LINES: Record<Theme['voice'], Record<Locale, string[]>> = {
  dry: {
    en: ['Nothing waiting.', 'The list is empty.', 'Clear.'],
    ja: ['待っているものはありません。', 'リストは空です。', '空です。'],
  },
  warm: {
    en: ['Nothing waiting. Rest is allowed.', 'All clear for now.', 'Nothing here. That’s fine.'],
    ja: ['何もありません。休んでいいです。', '今は空っぽです。', '何もない日もあります。'],
  },
  blunt: {
    en: ['Empty.', 'Nothing here.', 'Done for now.'],
    ja: ['空。', '何もない。', '今はここまで。'],
  },
  silly: {
    en: ['Nothing! Suspicious.', 'Empty. Go outside?', 'Zero tasks. Wild.'],
    ja: ['何もない！あやしい。', '空っぽ。外に出る？', 'ゼロ件。すごい。'],
  },
}

export function emptyLine(voice: Theme['voice'], locale: Locale, seed: number): string {
  const pool = VOICE_LINES[voice][locale]
  return pool[Math.abs(seed) % pool.length]
}

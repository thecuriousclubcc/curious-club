// 動画データの型定義と一覧
// YouTube Data API で自動取得する場合は、このファイルのデータ構造に合わせて差し替えてください

export interface Video {
  id: string
  youtubeId: string
  title: string
  description: string
  thumbnailUrl: string
  youtubeUrl: string
  publishedAt: string
  featured: boolean
  tags: string[]
}

export const videos: Video[] = [
  {
    id: '1',
    youtubeId: 'XubOV11LSnw',
    title: '#1 白石淳太さん　東大法学部から医学部へ',
    description:
      '東大法学部から医学部へという異色のキャリアを歩む白石淳太さんにインタビュー。なぜ法学部から医師の道を選んだのか、その決断と背景に迫ります。',
    thumbnailUrl: 'https://img.youtube.com/vi/XubOV11LSnw/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=XubOV11LSnw',
    publishedAt: '2025-05-10',
    featured: false,
    tags: ['医学生', 'キャリア', '東大'],
  },
  {
    id: '2',
    youtubeId: 'zMh0VrJs6qU',
    title: '#2 藤浦剛己先生　米盛病院研修医2年目　【医学生必見】',
    description:
      '米盛病院で研修医2年目として活躍する藤浦剛己先生に、研修医のリアルな日常と医師としての歩み方を語っていただきました。これから医師を目指す医学生必見の内容です。',
    thumbnailUrl: 'https://img.youtube.com/vi/zMh0VrJs6qU/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=zMh0VrJs6qU',
    publishedAt: '2025-05-18',
    featured: false,
    tags: ['研修医', '医学生', 'インタビュー'],
  },
  {
    id: '3',
    youtubeId: 'mM6oIZ_KX9M',
    title: '#3 中野知治院長　鹿児島三井中央クリニック　【美容外科のリアル】',
    description:
      '鹿児島三井中央クリニック院長の中野知治先生に生い立ちから今抱える問題、美容外科のリアルまでたっぷり語っていただきました！',
    thumbnailUrl: 'https://img.youtube.com/vi/mM6oIZ_KX9M/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=mM6oIZ_KX9M',
    publishedAt: '2025-05-18',
    featured: false,
    tags: ['医師', 'インタビュー', '美容外科'],
  },
  {
    id: '4',
    youtubeId: 'wyjwFxkeOGc',
    title: '#4 福元和彦理事長　福元クリニック　【日本唯一のTENGAドクター】',
    description:
      '「日本唯一のTENGAドクター」の福元和彦医師。性と医療に挑戦し続けるそのユニークなキャリアと哲学を、たっぷり2時間にわたって語っていただきました。',
    thumbnailUrl: 'https://img.youtube.com/vi/wyjwFxkeOGc/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=wyjwFxkeOGc',
    publishedAt: '2025-05-24',
    featured: false,
    tags: ['インタビュー', '泌尿器科', '医学生'],
  },
  {
    id: '5',
    youtubeId: 'xTfnvRmwavE',
    title: '#5 矢島正一代表取締役社長　株式会社AmaterZ　【元SONY社員が日本の農業に挑む】',
    description:
      '元SONY社員から農業ベンチャーへ転身した矢島正一氏。AmaterZ（アマテルズ）の挑戦と日本農業の未来、テクノロジーで農業を変える夢を語っていただきました。',
    thumbnailUrl: 'https://img.youtube.com/vi/xTfnvRmwavE/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=xTfnvRmwavE',
    publishedAt: '2025-06-02',
    featured: false,
    tags: ['起業家', '農業', 'ビジネス'],
  },
  {
    id: '6',
    youtubeId: 'fvIacGMrOA4',
    title: '#6 川尻強人会長　かごしまリアカー屋台組合　【鹿児島の街に屋台を】',
    description:
      '鹿児島の街に屋台文化を根付かせようとするかごしまリアカー屋台組合の川尻強人会長にインタビュー。地域を盛り上げる情熱と屋台への思いを語っていただきました。',
    thumbnailUrl: 'https://img.youtube.com/vi/fvIacGMrOA4/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=fvIacGMrOA4',
    publishedAt: '2025-06-12',
    featured: false,
    tags: ['地域活性化', '屋台', '鹿児島'],
  },
  {
    id: '7',
    youtubeId: '3ckOYhsil-c',
    title: '#7 福島大輔理事長　NPO法人桜島ミュージアム　【桜島博士】',
    description:
      '桜島を知り尽くす「桜島博士」こと福島大輔理事長。NPO法人桜島ミュージアムの活動と桜島への情熱、地域の自然を次世代に伝える活動について語っていただきました。',
    thumbnailUrl: 'https://img.youtube.com/vi/3ckOYhsil-c/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=3ckOYhsil-c',
    publishedAt: '2025-06-19',
    featured: false,
    tags: ['NPO', '桜島', '鹿児島'],
  },
  {
    id: '8',
    youtubeId: 'ju5qyS-xkwI',
    title: '#8 北薗巌院長　キタゾノクリニック　【夜間休日診療所と外科の二刀流】',
    description:
      '夜間休日診療所と外科クリニックを掛け持ちするキタゾノクリニック北薗巌院長。地域医療への貢献と二刀流の働き方、医師として歩んできた道を語っていただきました。',
    thumbnailUrl: 'https://img.youtube.com/vi/ju5qyS-xkwI/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=ju5qyS-xkwI',
    publishedAt: '2025-07-02',
    featured: false,
    tags: ['医師', '地域医療', '外科'],
  },
  {
    id: '9',
    youtubeId: 'QUFGS8W_U1Q',
    title: '#9 みやじ拓馬　自由民主党衆議院議員　【外務副大臣】',
    description:
      '外務副大臣を務める自由民主党衆議院議員のみやじ拓馬氏。政治家としての歩みと外交の現場、医療と政治の接点について語っていただきました。',
    thumbnailUrl: 'https://img.youtube.com/vi/QUFGS8W_U1Q/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=QUFGS8W_U1Q',
    publishedAt: '2025-07-11',
    featured: false,
    tags: ['政治', '外務', '衆議院'],
  },
  {
    id: '10',
    youtubeId: 'MyonD6FZHoc',
    title: '#10 山下積徳院長　つみのり内科クリニック　【りんご教室】',
    description:
      'つみのり内科クリニック院長・山下積徳先生。「りんご教室」という取り組みを通じた地域に根ざした診療の哲学と、患者さんとの向き合い方を語っていただきました。',
    thumbnailUrl: 'https://img.youtube.com/vi/MyonD6FZHoc/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=MyonD6FZHoc',
    publishedAt: '2025-08-07',
    featured: false,
    tags: ['医師', '地域医療', '内科'],
  },
  {
    id: '11',
    youtubeId: 'muF6JOq3SEU',
    title: '#11 小川晋平 代表取締役社長　AMI株式会社　【超聴診器】',
    description:
      'AIを活用した超聴診器を開発するAMI株式会社の小川晋平社長。医療×テクノロジーの最前線と起業家としての思い、日本の医療を変えるビジョンを語っていただきました。',
    thumbnailUrl: 'https://img.youtube.com/vi/muF6JOq3SEU/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=muF6JOq3SEU',
    publishedAt: '2025-08-15',
    featured: true,
    tags: ['医療テック', 'スタートアップ', 'AI'],
  },
  {
    id: '12',
    youtubeId: 'JPUYzEjEq8M',
    title: '#12 黒木康文院長　黒木医院　【地域医の哲学】',
    description:
      '阿久根で地域に根ざした診療を行う「黒木医院」黒木康文院長にインタビュー。救急から地域医療までの経験と反骨精神を背景に、"本当に必要な医療だけを届ける"という診療哲学と、医学生へのメッセージに迫ります。',
    thumbnailUrl: 'https://img.youtube.com/vi/JPUYzEjEq8M/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=JPUYzEjEq8M',
    publishedAt: '2025-09-20',
    featured: true,
    tags: ['阿久根市', '医療', '地域医療'],
  },
  {
    id: '13',
    youtubeId: 'fdQtMdO7JRA',
    title: '#13 手塚善久院長　手塚クリニック　【曽於医師会会長が語る志布志の地域医療】',
    description:
      '曽於医師会会長を務める手塚クリニックの手塚善久院長。志布志における地域医療の現状と課題、医師会の役割、そして地域の未来への展望を語っていただきました。',
    thumbnailUrl: 'https://img.youtube.com/vi/fdQtMdO7JRA/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=fdQtMdO7JRA',
    publishedAt: '2025-10-17',
    featured: true,
    tags: ['地域医療', '医師会', '鹿児島'],
  },
]

export const featuredVideos = videos.filter((v) => v.featured)

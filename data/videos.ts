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
    youtubeId: 'wyjwFxkeOGc',
    title: '#4 福元和彦理事長　福元クリニック　【日本唯一のTENGAドクター】',
    description:
      '「日本唯一のTENGAドクター」の福元和彦医師。性と医療に挑戦し続けるそのユニークなキャリアと哲学を、たっぷり2時間にわたって語っていただきました。',
    thumbnailUrl: 'https://img.youtube.com/vi/wyjwFxkeOGc/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=wyjwFxkeOGc',
    publishedAt: '2025-05-24',
    featured: true,
    tags: ['インタビュー', '泌尿器科', '医学生'],
  },
  {
    id: '2',
    youtubeId: 'mM6oIZ_KX9M',
    title: '#3 中野知治院長　鹿児島三井中央クリニック　【美容外科のリアル】',
    description:
      '鹿児島三井中央クリニック院長の中野知治先生に生い立ちから今抱える問題、美容外科のリアルまでたっぷり語っていただきました！',
    thumbnailUrl: 'https://img.youtube.com/vi/mM6oIZ_KX9M/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=mM6oIZ_KX9M',
    publishedAt: '2025-05-18',
    featured: true,
    tags: ['医師', 'インタビュー', '美容外科'],
  },
  {
    id: '3',
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
]

export const featuredVideos = videos.filter((v) => v.featured)

# The Curious Club（キュリクラ）公式サイト

YouTubeチャンネル「The Curious Club（キュリクラ）」の公式Webサイトです。
Next.js 14 + TypeScript + Tailwind CSS で構築されています。

## ページ構成

| パス | 内容 |
|------|------|
| `/` | トップページ（Hero / チャンネル紹介 / おすすめ動画 / CTA） |
| `/videos` | 動画一覧（YouTubeへ遷移） |
| `/about` | チャンネル概要・価値観・依頼の流れ |
| `/contact` | お問い合わせフォーム |

## 技術スタック

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Icons**: lucide-react
- **Font**: Noto Sans JP (Google Fonts via next/font)
- **Deploy**: Vercel

---

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/YOUR_USERNAME/curious-club.git
cd curious-club
```

### 2. 依存パッケージのインストール

```bash
# npm
npm install

# または pnpm
pnpm install
```

### 3. 開発サーバーを起動

```bash
npm run dev
# または
pnpm dev
```

ブラウザで [http://localhost:3000](http://localhost:3000) を開いてください。

---

## カスタマイズ

### 動画データの差し替え

`data/videos.ts` に動画データが集約されています。実際の動画情報に差し替えてください。

```ts
// data/videos.ts
export const videos: Video[] = [
  {
    id: '1',
    youtubeId: 'YOUR_YOUTUBE_VIDEO_ID',        // YouTubeの動画ID
    title: '動画タイトル',
    description: '動画の説明文',
    thumbnailUrl: 'https://img.youtube.com/vi/YOUR_YOUTUBE_VIDEO_ID/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=YOUR_YOUTUBE_VIDEO_ID',
    publishedAt: '2025-01-01',
    featured: true,  // trueにするとトップページに表示
    tags: ['タグ1', 'タグ2'],
  },
  // ...
]
```

> **将来的なYouTube API連携について**
> `data/videos.ts` の `Video` 型に合わせてAPIレスポンスをマッピングするだけで対応できます。

### SNSリンクの差し替え

`components/layout/Footer.tsx` の `socialLinks` 配列のURLを変更してください。

```ts
const socialLinks = [
  { href: 'https://www.youtube.com/@TheCuriousClub_CC', ... },
  { href: 'https://instagram.com/YOUR_ACCOUNT', ... },  // ← 差し替え
  { href: 'https://x.com/YOUR_ACCOUNT', ... },          // ← 差し替え
]
```

### お問い合わせフォームにメール送信を追加

`app/api/contact/route.ts` に、お好みのメール送信サービスを追加してください。

```ts
// Resend を使う例
import { Resend } from 'resend'
const resend = new Resend(process.env.RESEND_API_KEY)

await resend.emails.send({
  from: 'noreply@yourdomain.com',
  to: 'your@email.com',
  subject: `[お問い合わせ] ${type}`,
  text: `名前: ${name}\nメール: ${email}\n\n${message}`,
})
```

環境変数は `.env.local` に設定してください（`.gitignore` に含まれています）。

### OGP画像の設定

`public/og-image.png` に 1200×630px のOGP画像を配置してください。

---

## Vercelへのデプロイ

### 初回デプロイ

1. [Vercel](https://vercel.com) にサインアップ（GitHubアカウントで可）
2. GitHubにリポジトリをプッシュ
3. Vercelダッシュボードで「New Project」→ リポジトリを選択
4. Framework Preset が `Next.js` になっていることを確認
5. 「Deploy」をクリック

### 環境変数の設定（メール送信を使う場合）

Vercelダッシュボード → Project Settings → Environment Variables に追加：

```
RESEND_API_KEY=re_xxxxxxxxxxxx
```

### カスタムドメインの設定

Vercelダッシュボード → Project → Domains からドメインを追加できます。

---

## ビルド確認

```bash
npm run build
npm run start
```

エラーなくビルドが完了すれば、本番環境へのデプロイ準備完了です。

---

## ライセンス

© The Curious Club. All rights reserved.

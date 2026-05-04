# cue

DaVinci Resolve Studio 20 (Windows) 用の演出自動化ツール。

タイムラインに打ったマーカーを起点に、ドキュメンタリー風の映像演出(矢印、囲み枠、注釈、章タイトル、ズーム等)を自動付与します。

## コンセプト

- **マーカー起点の自動演出**: タイムラインのマーカー位置に、選択したエフェクトを一括配置
- **クリック中心の UI**: マウス操作とプリセット選択だけで完結。こだわりたい場合のみ数値入力で微調整
- **拡張可能な設計**: マーカー以外のトリガー(将来のクリック検出、音声解析など)、矢印以外のエフェクト(囲み枠、注釈、章タイトル、ズーム)を後から差し込める構造

## MVP: 矢印演出

現在実装済みの機能:

- タイムライン上のマーカー一覧表示
- マーカー色によるフィルタリング(複数選択可)
- 8方向プリセット (右上 / 右 / 右下 / 下 / 左下 / 左 / 左上 / 上 / 中央指し)
- 表示位置・サイズ・表示時間・フェードイン/アウトの数値調整
- プレビュー専用トラック (`cue_preview`) への仮配置
- 全マーカーへの一括適用 (デフォルト V3)
- 既存配置に対する「上書き / スキップ」選択

## インストール

1. このリポジトリをクローンまたはダウンロード
2. `cue/` ディレクトリと `cue.py` を以下にコピー:

   ```
   %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Comp\
   ```

   配置後の構造:

   ```
   …\Scripts\Comp\
   ├── cue.py
   └── cue\
       ├── __init__.py
       ├── core\
       ├── effects\
       └── …
   ```

3. 矢印 PNG 素材を `cue/assets/arrows/` に配置 (ファイル名規約は後述)
4. Fusion テンプレ (`.setting`) を `cue/assets/templates/` に配置

## 使い方

1. DaVinci Resolve でタイムラインを開く
2. 演出を入れたい位置にマーカーを打つ (色は何でも OK)
3. メニューから **Workspace > Scripts > cue** を選択
4. GUI でマーカー色を選択し、矢印プリセットを選び、「全マーカーに適用」

## アセット規約

### 矢印 PNG (`cue/assets/arrows/`)

ファイル名は **矢印の根元位置** (画面のどこに矢印が表示されるか) ベース:

| ファイル名         | 方向                   |
| ------------------ | ---------------------- |
| `arrow_tr.png`     | 右上 (top-right)       |
| `arrow_r.png`      | 右   (right)           |
| `arrow_br.png`     | 右下 (bottom-right)    |
| `arrow_b.png`      | 下   (bottom)          |
| `arrow_bl.png`     | 左下 (bottom-left)     |
| `arrow_l.png`      | 左   (left)            |
| `arrow_tl.png`     | 左上 (top-left)        |
| `arrow_t.png`      | 上   (top)             |
| `arrow_c.png`      | 中央指し (center)      |

PNG は透過背景、推奨 1920x1080 (位置決めはエフェクト側で正規化座標 0.0-1.0 を使う)。

### Fusion テンプレ (`cue/assets/templates/`)

各エフェクトは Fusion Composition (`.setting` ファイル) を読み込んでパラメータを差し替える形で適用されます。

| ファイル名              | 用途                       |
| ----------------------- | -------------------------- |
| `arrow.setting`         | 矢印エフェクト用テンプレ   |

テンプレ内には以下の Fusion ノードを含む想定:

- `MediaIn1`: 矢印 PNG の入力
- `Transform1`: 位置・スケール調整
- `Merge1`: ベース映像との合成 (Blend をキーフレーム化してフェード制御)

## 配置されるクリップの命名規約

衝突検出のため、本ツールが配置するクリップには以下の名前を付けます:

```
cue_<effect>_<color>_f<frame>
例: cue_arrow_Red_f12345
```

ユーザーがこのクリップ名を変更しなければ、再実行時の上書き / スキップが正しく機能します。

## 設計

### モジュール構造

```
cue/
├── cue.py                    # Resolve から呼ぶエントリーポイント
└── cue/
    ├── config.py             # 定数・パス・デフォルト値
    ├── core/
    │   ├── resolve_api.py    # Resolve への接続 (テスト時はモック差し替え)
    │   ├── markers.py        # マーカー取得・色フィルタ
    │   └── timeline.py       # タイムライン/トラック操作
    ├── triggers/
    │   ├── base.py           # Trigger 基底クラス
    │   └── marker_trigger.py # マーカー由来のトリガー
    ├── effects/
    │   ├── base.py           # Effect 基底クラス + Params/Result/Context
    │   ├── context.py
    │   └── arrow.py          # 矢印エフェクト
    ├── ui/
    │   ├── main_window.py
    │   └── arrow_panel.py
    └── assets/
        ├── arrows/
        └── templates/
```

### トリガーとエフェクトの分離

- **Trigger** = 「いつ・どこで」発火するか (マーカー、クリック、音声検出 …)
- **Effect** = 「何を」配置するか (矢印、囲み枠、注釈 …)

両者は `EffectContext` を介して疎結合になっており、新しい Trigger や Effect を独立に追加できます。

## 開発

```bash
pip install -e ".[dev]"
pytest
```

Resolve 実機がない環境でも、`tests/fixtures/` の API レスポンスサンプルでロジック層をテスト可能です。

## ロードマップ

### Phase 1 (MVP, 現在)

- 矢印エフェクト (8方向離散)

### Phase 2

- 矢印の自由角度対応 (PNG 回転または Fusion ノード描画)
- 囲み枠エフェクト
- 注釈 (テキスト) エフェクト

### Phase 3

- 章タイトルエフェクト
- ズームエフェクト
- マーカー以外のトリガー (クリック検出、音声解析)
- プリセットの保存・共有

## ライセンス

未定。

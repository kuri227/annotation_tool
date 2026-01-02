import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import os
import sys
import platform

# 音声制御のためにpygameを使用
try:
  import pygame
  HAS_PYGAME = True
except ImportError:
  HAS_PYGAME = False

class AudioAnnotationApp:
  def __init__(self, root):
    self.root = root
    self.root.title("Audio Annotation Tool (Enhanced Player)")
    self.root.geometry("1000x750")

    # pygame初期化（音声ミキサー）
    if HAS_PYGAME:
      pygame.mixer.init()
    else:
      messagebox.showwarning(
          "ライブラリ不足", "pygameがインストールされていません。\n再生機能を利用するには 'pip install pygame' を実行してください。")

    # データ管理用変数
    self.file_data = []
    self.labels = []
    self.use_numeric = False

    # 再生状態管理
    self.is_paused = False
    self.current_playing_path = None

    # フォント設定
    self.default_font = ("Yu Gothic UI", 10)
    self.style = ttk.Style()
    self.style.configure("Treeview", font=self.default_font, rowheight=25)
    self.style.configure("TButton", font=self.default_font)

    # アプリケーションのフェーズ管理
    self.setup_ui_phase()

  def setup_ui_phase(self):
    """初期設定画面：ラベル定義"""
    self.clear_window()

    frame = ttk.Frame(self.root, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="1. ラベル設定", font=(
        "Yu Gothic UI", 16, "bold")).pack(pady=10)

    desc = "分類したいクラス名（例: victim, rescuer, environment）を追加してください。\n数値（0.0〜1.0など）でスコア付けしたい場合はチェックを入れてください。"
    ttk.Label(frame, text=desc).pack(pady=5)

    # ラベル追加エリア
    input_frame = ttk.Frame(frame)
    input_frame.pack(pady=10)

    self.entry_label_name = ttk.Entry(input_frame, width=20)
    self.entry_label_name.pack(side=tk.LEFT, padx=5)
    self.entry_label_name.bind(
        '<Return>', lambda event: self.add_label_candidate())

    ttk.Button(input_frame, text="追加",
               command=self.add_label_candidate).pack(side=tk.LEFT)

    self.listbox_labels = tk.Listbox(frame, height=6)
    self.listbox_labels.pack(pady=10, fill=tk.X, padx=50)

    self.var_use_numeric = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text="数値入力（スコア）も使用する",
                    variable=self.var_use_numeric).pack(pady=5)

    ttk.Button(frame, text="設定完了してアノテーションを開始",
               command=self.finish_setup).pack(pady=20)

    # デフォルト例
    default_labels = ["victim", "rescuer", "environment"]
    for l in default_labels:
      self.labels.append(l)
      self.listbox_labels.insert(tk.END, l)

  def add_label_candidate(self):
    text = self.entry_label_name.get().strip()
    if text and text not in self.labels:
      self.labels.append(text)
      self.listbox_labels.insert(tk.END, text)
      self.entry_label_name.delete(0, tk.END)

  def finish_setup(self):
    self.use_numeric = self.var_use_numeric.get()
    if not self.labels and not self.use_numeric:
      messagebox.showwarning("警告", "ラベルまたは数値入力のどちらかは設定してください。")
      return
    self.main_ui_phase()

  def clear_window(self):
    for widget in self.root.winfo_children():
      widget.destroy()

  # =========================================================
  # メイン画面
  # =========================================================
  def main_ui_phase(self):
    self.clear_window()

    # 上部ツールバー
    top_frame = ttk.Frame(self.root, padding=5)
    top_frame.pack(side=tk.TOP, fill=tk.X)

    ttk.Button(top_frame, text="音声ファイルを追加",
               command=self.load_files).pack(side=tk.LEFT, padx=5)
    ttk.Button(top_frame, text="CSV出力 (保存)",
               command=self.export_csv).pack(side=tk.RIGHT, padx=5)

    # メインエリア（左右分割）
    paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
    paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # 左パネル：リスト
    left_frame = ttk.Frame(paned)
    paned.add(left_frame, weight=1)

    columns = ("filename", "label")
    self.tree = ttk.Treeview(
        left_frame, columns=columns, show="headings", selectmode="browse")
    self.tree.heading("filename", text="ファイル名 (書き出し用)")
    self.tree.heading("label", text="ラベル")
    self.tree.column("filename", width=200)
    self.tree.column("label", width=100)

    scrollbar = ttk.Scrollbar(
        left_frame, orient=tk.VERTICAL, command=self.tree.yview)
    self.tree.configure(yscroll=scrollbar.set)

    self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    self.tree.bind("<<TreeviewSelect>>", self.on_item_select)

    # 右パネル：編集エリア
    right_frame = ttk.Frame(paned, padding=10)
    paned.add(right_frame, weight=1)

    self.create_editor_panel(right_frame)

  def create_editor_panel(self, parent):
    lbl_frame = ttk.LabelFrame(parent, text="編集・再生", padding=10)
    lbl_frame.pack(fill=tk.BOTH, expand=True)

    # --- ファイル情報 ---
    ttk.Label(lbl_frame, text="元ファイル:").pack(anchor=tk.W)
    self.lbl_original_path = ttk.Label(
        lbl_frame, text="未選択", foreground="gray", wraplength=300)
    self.lbl_original_path.pack(anchor=tk.W, pady=(0, 10))

    # --- 強化された再生コントロール ---
    control_frame = ttk.LabelFrame(lbl_frame, text="オーディオコントロール", padding=5)
    control_frame.pack(fill=tk.X, pady=(0, 15))

    # ボタン群
    btn_box = ttk.Frame(control_frame)
    btn_box.pack(fill=tk.X, pady=5)

    self.btn_play_pause = ttk.Button(
        btn_box, text="▶ 再生", command=self.toggle_play_pause, state=tk.DISABLED, width=10)
    self.btn_play_pause.pack(side=tk.LEFT, padx=5)

    self.btn_stop = ttk.Button(
        btn_box, text="■ 停止", command=self.stop_audio, state=tk.DISABLED, width=8)
    self.btn_stop.pack(side=tk.LEFT, padx=5)

    # 音量スライダー
    vol_box = ttk.Frame(control_frame)
    vol_box.pack(fill=tk.X, pady=5)
    ttk.Label(vol_box, text="音量:").pack(side=tk.LEFT)
    self.scale_volume = ttk.Scale(
        vol_box, from_=0.0, to=1.0, value=0.5, orient=tk.HORIZONTAL, command=self.change_volume)
    self.scale_volume.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    # --- ファイル名変更 ---
    ttk.Label(lbl_frame, text="ファイル名 (CSV出力時):").pack(anchor=tk.W)
    self.entry_filename = ttk.Entry(lbl_frame)
    self.entry_filename.pack(fill=tk.X, pady=(0, 10))
    self.entry_filename.bind('<KeyRelease>', self.update_filename_live)

    # --- ラベル付与エリア ---
    ttk.Separator(lbl_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
    ttk.Label(lbl_frame, text="ラベル割り当て:", font=(
        "", 11, "bold")).pack(anchor=tk.W)

    btn_container = ttk.Frame(lbl_frame)
    btn_container.pack(fill=tk.X, pady=5)

    self.class_buttons = []
    for label_text in self.labels:
      btn = tk.Button(btn_container, text=label_text, bg="#e0e0e0",
                      command=lambda l=label_text: self.set_label(l))
      btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)
      self.class_buttons.append(btn)

    if self.use_numeric:
      num_frame = ttk.Frame(lbl_frame)
      num_frame.pack(fill=tk.X, pady=10)
      ttk.Label(num_frame, text="数値スコア:").pack(side=tk.LEFT)
      self.entry_score = ttk.Entry(num_frame, width=10)
      self.entry_score.pack(side=tk.LEFT, padx=5)
      ttk.Button(num_frame, text="設定",
                 command=self.set_numeric_label).pack(side=tk.LEFT)

  # =========================================================
  # ロジック
  # =========================================================
  def load_files(self):
    filetypes = [
        ("Audio Files", "*.wav *.mp3 *.flac *.m4a *.ogg"), ("All Files", "*.*")]
    paths = filedialog.askopenfilenames(
        title="音声ファイルを選択", filetypes=filetypes)

    for path in paths:
      filename = os.path.basename(path)
      item = {
          'original_path': path,
          'export_name': filename,
          'label': ""
      }
      self.file_data.append(item)
      idx = len(self.file_data) - 1
      self.tree.insert("", tk.END, iid=str(idx), values=(filename, ""))

  def on_item_select(self, event):
    # ファイル切り替え時は再生停止
    self.stop_audio()

    selected_items = self.tree.selection()
    if not selected_items:
      return

    idx = int(selected_items[0])
    data = self.file_data[idx]

    self.lbl_original_path.config(text=data['original_path'])
    self.entry_filename.delete(0, tk.END)
    self.entry_filename.insert(0, data['export_name'])

    # 再生コントロールの有効化
    if HAS_PYGAME:
      self.btn_play_pause.config(state=tk.NORMAL, text="▶ 再生")
      self.btn_stop.config(state=tk.NORMAL)

    # ラベルボタンの色更新
    current_label = data['label']
    for btn in self.class_buttons:
      if str(current_label) == btn['text']:
        btn.config(bg="#aaccff", relief=tk.SUNKEN)
      else:
        btn.config(bg="#e0e0e0", relief=tk.RAISED)

    if self.use_numeric and self.is_number(current_label):
      self.entry_score.delete(0, tk.END)
      self.entry_score.insert(0, str(current_label))
    elif self.use_numeric:
      self.entry_score.delete(0, tk.END)

  def is_number(self, s):
    try:
      float(s)
      return True
    except ValueError:
      return False

  def update_filename_live(self, event):
    selected_items = self.tree.selection()
    if not selected_items: return
    idx = int(selected_items[0])
    new_name = self.entry_filename.get()
    self.file_data[idx]['export_name'] = new_name
    self.tree.set(str(idx), column="filename", value=new_name)

  def set_label(self, label_value):
    selected_items = self.tree.selection()
    if not selected_items: return
    idx = int(selected_items[0])
    self.file_data[idx]['label'] = label_value
    self.tree.set(str(idx), column="label", value=label_value)
    self.on_item_select(None)

    # 次の行へ移動
    next_idx = idx + 1
    if next_idx < len(self.file_data):
      self.tree.selection_set(str(next_idx))
      self.tree.see(str(next_idx))

  def set_numeric_label(self):
    val = self.entry_score.get()
    if self.is_number(val):
      self.set_label(val)
    else:
      messagebox.showerror("エラー", "数値を入力してください")

  # =========================================================
  # オーディオ制御ロジック (Pygame)
  # =========================================================
  def toggle_play_pause(self):
    if not HAS_PYGAME: return

    # 既に再生中でポーズ状態の場合 -> 再開
    if pygame.mixer.music.get_busy():
      if self.is_paused:
        pygame.mixer.music.unpause()
        self.is_paused = False
        self.btn_play_pause.config(text="|| 一時停止")
      else:
        pygame.mixer.music.pause()
        self.is_paused = True
        self.btn_play_pause.config(text="▶ 再開")
    else:
      # 停止中、または初回再生
      selected_items = self.tree.selection()
      if not selected_items: return
      idx = int(selected_items[0])
      path = self.file_data[idx]['original_path']

      if not os.path.exists(path):
        messagebox.showerror("エラー", "ファイルが見つかりません")
        return

      try:
        # 読み込みと再生
        pygame.mixer.music.load(path)
        # 現在の音量スライダーの値を適用
        vol = self.scale_volume.get()
        pygame.mixer.music.set_volume(vol)

        pygame.mixer.music.play()
        self.is_paused = False
        self.btn_play_pause.config(text="|| 一時停止")
        self.current_playing_path = path
      except Exception as e:
        messagebox.showerror("再生エラー", f"再生できませんでした: {e}")

  def stop_audio(self):
    if not HAS_PYGAME: return
    pygame.mixer.music.stop()
    # ファイルロック解除のためにunload（pygame 2.0.0以降推奨）
    try:
      pygame.mixer.music.unload()
    except AttributeError:
      pass  # 古いバージョンの場合はunloadがない

    self.is_paused = False
    self.btn_play_pause.config(text="▶ 再生")

  def change_volume(self, val):
    if not HAS_PYGAME: return
    volume = float(val)
    pygame.mixer.music.set_volume(volume)

  # =========================================================
  # エクスポート処理
  # =========================================================
  def export_csv(self):
    # 安全のため再生停止
    self.stop_audio()

    if not self.file_data:
      messagebox.showinfo("info", "データがありません")
      return

    save_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV Files", "*.csv")],
        title="CSVファイルの保存場所を選択",
        initialfile="label_data.csv"
    )
    if not save_path:
      return

    do_rename = messagebox.askyesno(
        "ファイル名変更の確認",
        "CSVに出力するファイル名に合わせて、\n実際の音声ファイル名も変更（リネーム）しますか？"
    )

    try:
      with open(save_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "label"])

        for item in self.file_data:
          final_name = item['export_name']
          label = item['label']
          writer.writerow([final_name, label])

          if do_rename:
            original_dir = os.path.dirname(item['original_path'])
            new_path = os.path.join(original_dir, final_name)

            if item['original_path'] != new_path:
              try:
                os.rename(item['original_path'], new_path)
                item['original_path'] = new_path
              except OSError as e:
                print(f"Rename Error: {e}")

      messagebox.showinfo("完了", f"保存しました: {save_path}")

    except Exception as e:
      messagebox.showerror("エラー", f"保存中にエラーが発生しました: {e}")

if __name__ == "__main__":
  root = tk.Tk()
  app = AudioAnnotationApp(root)
  root.mainloop()

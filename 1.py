"""숲의 나방 유전 알고리즘 시각화. Python 표준 라이브러리 Tkinter만 사용합니다."""
import random
import tkinter as tk
from tkinter import ttk

N_GENERATIONS = 10  # 첫 무작위 개체군을 1세대로 포함
POP_SIZE = 12
PALETTE = [
    (42, 103, 65), (80, 130, 74), (130, 161, 83), (177, 151, 92),
    (104, 75, 55), (70, 119, 132), (180, 111, 73), (196, 184, 141),
    (119, 91, 143), (218, 119, 145),
]
COLOR_NAMES = ["숲 초록", "잎 초록", "연두", "황갈색", "나무 갈색", "청록", "주황 갈색", "베이지", "보라", "분홍"]
BARK_PALETTE = [
    (76, 43, 29), (94, 54, 35), (111, 65, 42), (128, 76, 49), (145, 88, 57),
    (158, 101, 67), (126, 80, 58), (171, 116, 79), (102, 70, 52), (190, 137, 94),
]
LEAF_PALETTE = [(43, 105, 55), (57, 127, 62), (75, 145, 68), (91, 157, 78)]


def hx(rgb):
    return "#%02x%02x%02x" % rgb


def distance(a, b):
    return sum((x-y)**2 for x, y in zip(a, b)) ** 0.5


class Moth:
    def __init__(self, colors=None, spots=None):
        self.colors = list(colors) if colors is not None else [random.randrange(10) for _ in range(3)]
        self.spots = spots if spots is not None else random.randint(2, 6)
        self.score = 0.0
        self.mutations = set()


class MothGA:
    def __init__(self, root):
        self.root = root
        root.title("나방의 유전 알고리즘 · 10세대 시각화")
        root.configure(bg="#eef2e8")
        self.generation = 1
        self.mutation_rate = tk.DoubleVar(value=0.12)
        self.running = False
        self.phase = "초기 개체군 평가 완료 · 부모 선택 대기"
        self.bark_base = 0
        self.bark_patches = []
        self.moths = [Moth() for _ in range(POP_SIZE)]
        self.parents = []
        self.children = []
        self.child_index = 0
        self.selected = None
        self.history_best, self.history_avg = [], []
        self._build_ui()
        self.new_forest()
        self.evaluate()
        self.draw()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        bar = tk.Frame(self.root, bg="#eef2e8", padx=12, pady=8)
        bar.pack(fill="x")
        tk.Label(bar, text="숲에 가장 잘 어울리는 나방은?", font=("맑은 고딕", 18, "bold"),
                 bg="#eef2e8", fg="#23442e").pack(side="left")
        self.status = tk.Label(bar, text="", font=("맑은 고딕", 10, "bold"), bg="#eef2e8", fg="#385b41")
        self.status.pack(side="right")

        controls = tk.Frame(self.root, bg="#eef2e8", padx=12, pady=4)
        controls.pack(fill="x")
        self.step_button = ttk.Button(controls, text="다음 단계", command=self.step)
        self.step_button.pack(side="left", padx=(0, 6))
        self.auto_button = ttk.Button(controls, text="자동 실행", command=self.toggle_auto)
        self.auto_button.pack(side="left", padx=(0, 12))
        self.forest_button = ttk.Button(controls, text="새 숲", command=self.change_forest)
        self.forest_button.pack(side="left", padx=(0, 12))
        tk.Label(controls, text="변이 확률", bg="#eef2e8", font=("맑은 고딕", 9)).pack(side="left")
        self.rate_scale = tk.Scale(controls, variable=self.mutation_rate, from_=0, to=.5, resolution=.01,
                                   orient="horizontal", length=130, bg="#eef2e8", highlightthickness=0)
        self.rate_scale.pack(side="left")
        tk.Label(controls, text="초기 개체군도 1세대로 계산 · 총 10세대", bg="#eef2e8",
                 font=("맑은 고딕", 9), fg="#53634f").pack(side="right")

        self.canvas = tk.Canvas(self.root, width=1100, height=700, bg="#dce8cf", highlightthickness=0)
        self.canvas.pack(padx=10, pady=(2, 10), fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_click)

    def new_forest(self):
        # 몸통의 바탕과 무늬를 10가지 갈색 계열로 무작위 배치한다.
        self.bark_base = random.randrange(10)
        self.bark_patches = []
        for _ in range(180):
            x = random.uniform(95, 1005)
            y = random.uniform(125, 665)
            rx, ry = random.randint(15, 52), random.randint(12, 38)
            left_edge = 110 - (y-80)*100/620
            right_edge = 990 + (y-80)*100/620
            if left_edge+rx+10 <= x <= right_edge-rx-10:
                self.bark_patches.append({"x": x, "y": y, "rx": rx, "ry": ry,
                                          "color": random.randrange(10)})

    def change_forest(self):
        self.new_forest()
        self.generation = 1
        self.moths = [Moth() for _ in range(POP_SIZE)]
        self.parents = []
        self.children = []
        self.selected = None
        self.history_best, self.history_avg = [], []
        self.evaluate()
        self.phase = "초기 개체군 평가 완료 · 부모 선택 대기"
        self.running = False
        self.step_button.configure(state="normal")
        self.auto_button.configure(text="자동 실행")
        self.draw()

    def tree_color_at(self, x, y):
        # 시료 픽셀은 몸통 내부에서만 채점한다.
        if not 80 <= y <= 700:
            return BARK_PALETTE[self.bark_base]
        left_edge = 110 - (y-80)*100/620
        right_edge = 990 + (y-80)*100/620
        if not left_edge <= x <= right_edge:
            return BARK_PALETTE[self.bark_base]
        for patch in reversed(self.bark_patches):
            if ((x-patch["x"])/patch["rx"])**2 + ((y-patch["y"])/patch["ry"])**2 <= 1:
                return BARK_PALETTE[patch["color"]]
        return BARK_PALETTE[self.bark_base]

    @staticmethod
    def position(i):
        return 155 + (i % 6)*158, 195 + (i // 6)*195

    def fitness(self, moth, i):
        # 날개가 차지하는 픽셀을 표본화하여 겹친 나무/숲 픽셀과 RGB 거리 계산.
        cx, cy = self.position(i)
        total, count = 0.0, 0
        for side in (-1, 1):
            for px in range(0, 54, 3):
                for py in range(0, 36, 3):
                    if py > 36*(1-px/54)+7:  # 날개 윤곽 밖
                        continue
                    bg = self.tree_color_at(cx + side*(7+px*.72), cy-5+py*.72)
                    wing = PALETTE[moth.colors[(px//9) % 3]]
                    total += distance(bg, wing)
                    count += 1
        avg = total / max(count, 1)
        # 최대 RGB 거리로 정규화: 거리가 가까울수록 적합도(%)가 높음.
        return max(0.0, 100.0*(1.0-avg/(3**.5*255)))

    def evaluate(self):
        for i, moth in enumerate(self.moths):
            moth.score = self.fitness(moth, i)
        self.history_best.append(max(m.score for m in self.moths))
        self.history_avg.append(sum(m.score for m in self.moths)/len(self.moths))

    def select_parent(self):
        # 룰렛 휠 선택: 적합도가 높은 개체가 부모가 될 확률이 높음.
        return random.choices(self.moths, weights=[m.score+1 for m in self.moths], k=1)[0]

    def step(self):
        if self.generation >= N_GENERATIONS and self.phase.startswith("완료"):
            return
        if self.phase.startswith("초기 개체군") or self.phase.startswith("세대 교체 완료") or self.phase.startswith("환경 변경"):
            self.parents = [self.select_parent(), self.select_parent()]
            self.phase = "선택 완료 · 부모 강조 표시"
        elif self.phase.startswith("선택 완료"):
            self.children = []
            for _ in range(POP_SIZE-1):
                a, b = self.select_parent(), self.select_parent()
                colors = [a.colors[j] if random.random() < .5 else b.colors[j] for j in range(3)]
                spots = a.spots if random.random() < .5 else b.spots
                self.children.append(Moth(colors, spots))
            self.children.insert(0, Moth(max(self.moths, key=lambda m: m.score).colors,
                                         max(self.moths, key=lambda m: m.score).spots))
            self.child_index = 0
            self.phase = "교차 완료 · 자식 유전자 구성"
        elif self.phase.startswith("교차 완료"):
            rate = self.mutation_rate.get()
            for child in self.children[1:]:
                for j in range(3):
                    if random.random() < rate:
                        child.colors[j] = random.randrange(10)
                        child.mutations.add(j)
                if random.random() < rate:
                    child.spots = random.randint(2, 6)
                    child.mutations.add(3)
            self.phase = "변이 완료 · 변이 표식 확인"
        elif self.phase.startswith("변이 완료"):
            if self.generation < N_GENERATIONS:
                self.moths = self.children
                self.generation += 1
                self.evaluate()
                if self.generation == N_GENERATIONS:
                    self.phase = "완료 · 10세대 결과 유지 중"
                    self._set_finished_controls()
                else:
                    self.phase = "세대 교체 완료 · 새 개체군 평가"
            else:
                self.phase = "완료 · 10세대 결과 유지 중"
                self._set_finished_controls()
        else:
            # 세대 10은 그대로 두고 종료 상태로 전환
            self.phase = "완료 · 10세대 결과 유지 중"
            self._set_finished_controls()
        self.draw()

    def _set_finished_controls(self):
        self.running = False
        self.auto_button.configure(text="자동 실행")
        self.step_button.configure(state="disabled")

    def toggle_auto(self):
        if self.phase.startswith("완료"):
            return
        self.running = not self.running
        self.auto_button.configure(text="일시정지" if self.running else "자동 실행")
        if self.running:
            self._auto_tick()

    def _auto_tick(self):
        if not self.running:
            return
        self.step()
        if self.running:
            self.root.after(800, self._auto_tick)

    def _status(self):
        self.status.configure(text=f"세대 {self.generation}/{N_GENERATIONS}  ·  {self.phase}")

    def on_click(self, event):
        for i, moth in enumerate(self.moths):
            x, y = self.position(i)
            if abs(event.x-x) < 75 and abs(event.y-y) < 60:
                self.selected = i
                self.draw()
                names = " → ".join(f"{COLOR_NAMES[c]}({c})" for c in moth.colors)
                self.canvas.create_rectangle(12, 435, 1085, 485, fill="#fffdf4", outline="#9eac91", tags="detail")
                self.canvas.create_text(22, 443, anchor="nw", width=1040, tags="detail",
                    text=f"선택한 나방 #{i+1} · 적합도 {moth.score:.1f}% · 날개색 순서: {names} → 반복 · 무늬 수: {moth.spots} · 변이 유전자: {', '.join(map(str, sorted(moth.mutations))) or '없음'}",
                    font=("맑은 고딕", 9), fill="#263b2b")
                break

    def draw_moth(self, x, y, moth, index):
        outline = "#f4c84a" if index in [self.moths.index(p) for p in self.parents if p in self.moths] else "#566650"
        if self.selected == index:
            outline = "#3448aa"
        self.canvas.create_oval(x-6, y-19, x+6, y+20, fill="#594b3f", outline=outline, width=2)
        # 좌우 날개 픽셀의 색 띠는 동일한 3색 순서를 반복
        for side in (-1, 1):
            for stripe in range(6):
                color = hx(PALETTE[moth.colors[(stripe//2) % 3]])
                near = x + side*(7+stripe*8)
                far = x + side*(15+stripe*8)
                top = y-17+stripe*2
                bottom = top+34-stripe*3
                self.canvas.create_polygon(near, top, far, top+5, far, bottom, near, bottom-3,
                                           fill=color, outline=outline, width=1)
        for j in range(moth.spots):
            sx, sy = x-22+(j%3)*19, y-7+(j//3)*12
            self.canvas.create_oval(sx-2, sy-2, sx+2, sy+2, fill=hx(PALETTE[moth.colors[1]]), outline="")
        self.canvas.create_text(x, y+37, text=f"#{index+1}  {moth.score:.1f}%", font=("맑은 고딕", 9, "bold"), fill="#263b2b")
        if moth.mutations:
            self.canvas.create_text(x+55, y-28, text="✦ 변이", font=("맑은 고딕", 9, "bold"), fill="#c0442e")

    def draw_graph(self):
        left, right, top, bottom = 82, 1070, 510, 610
        self.canvas.create_rectangle(12, 492, 1085, 694, fill="#f8faef", outline="#8a9c80")
        self.canvas.create_text(23, 496, anchor="nw", text="x축: 세대  ·  y축: 적합도 (%)", font=("맑은 고딕", 10, "bold"), fill="#314a35")
        self.canvas.create_text(22, 548, text="y축\n적합도(%)", font=("맑은 고딕", 8, "bold"), fill="#314a35")
        for value in (0, 25, 50, 75, 100):
            yy = bottom - value
            self.canvas.create_line(left, yy, right, yy, fill="#d7dfd0", width=1)
            self.canvas.create_text(left-8, yy, text=str(value), anchor="e", font=("맑은 고딕", 8), fill="#52634f")
        self.canvas.create_line(left, top, left, bottom, fill="#667660")
        self.canvas.create_line(left, bottom, right, bottom, fill="#667660")
        n = len(self.history_best)
        best_pts, avg_pts = [], []
        x_positions = []
        for i, (best, avg) in enumerate(zip(self.history_best, self.history_avg)):
            xx = left + i*(right-left)/(N_GENERATIONS-1)
            x_positions.append(xx)
            best_pts += [xx, bottom-best]
            avg_pts += [xx, bottom-avg]
            self.canvas.create_line(xx, bottom, xx, bottom+4, fill="#667660")
            self.canvas.create_text(xx, bottom+8, text=str(i+1), anchor="n", font=("맑은 고딕", 8), fill="#263b2b")
        if len(best_pts) >= 4:
            self.canvas.create_line(*best_pts, fill="#d47736", width=2, smooth=True)
            self.canvas.create_line(*avg_pts, fill="#477c55", width=2, smooth=True)
        for xx, yy in zip(best_pts[::2], best_pts[1::2]):
            self.canvas.create_oval(xx-2.5, yy-2.5, xx+2.5, yy+2.5, fill="#d47736", outline="")
        for xx, yy in zip(avg_pts[::2], avg_pts[1::2]):
            self.canvas.create_oval(xx-2.5, yy-2.5, xx+2.5, yy+2.5, fill="#477c55", outline="")
        self.canvas.create_text(890, 498, anchor="nw", text="● 최고 적합도 (%)", font=("맑은 고딕", 8), fill="#d47736")
        self.canvas.create_text(1010, 498, anchor="nw", text="● 평균 (%)", font=("맑은 고딕", 8), fill="#477c55")
        # 그래프 아래 표에 세대별 실제 수치를 그대로 표시
        self.canvas.create_text(22, 649, anchor="w", text="최고", font=("맑은 고딕", 8, "bold"), fill="#d47736")
        self.canvas.create_text(22, 670, anchor="w", text="평균", font=("맑은 고딕", 8, "bold"), fill="#477c55")
        for i, xx in enumerate(x_positions):
            if i < len(self.history_best):
                self.canvas.create_text(xx, 649, text=f"{self.history_best[i]:.1f}", font=("맑은 고딕", 7), fill="#a95825")
                self.canvas.create_text(xx, 670, text=f"{self.history_avg[i]:.1f}", font=("맑은 고딕", 7), fill="#356441")

    def draw(self):
        self.canvas.delete("all")
        self._status()
        self.canvas.create_rectangle(0, 0, 1100, 700, fill="#dce8cf", outline="")
        # 잎은 초록 계열, 몸통은 갈색 계열로 분리해 그린다.
        self.canvas.create_oval(28, -95, 1072, 235, fill=hx(LEAF_PALETTE[1]), outline="#315e39", width=3)
        for k in range(38):
            x = random.randint(35, 1065)
            y = random.randint(-55, 225)
            rx, ry = random.randint(18, 55), random.randint(15, 38)
            if ((x-550)/515)**2 + ((y-70)/165)**2 <= 1:
                self.canvas.create_oval(x-rx, y-ry, x+rx, y+ry,
                                        fill=hx(random.choice(LEAF_PALETTE)), outline="")
        # 하나의 넓은 몸통 안쪽에 나방 12마리가 모두 위치한다.
        trunk = [110, 80, 990, 80, 1090, 700, 10, 700]
        self.canvas.create_polygon(*trunk, fill=hx(BARK_PALETTE[self.bark_base]), outline="#553522", width=4)
        for patch in self.bark_patches:
            x, y, rx, ry = patch["x"], patch["y"], patch["rx"], patch["ry"]
            self.canvas.create_oval(x-rx, y-ry, x+rx, y+ry,
                                    fill=hx(BARK_PALETTE[patch["color"]]), outline="")
        self.canvas.create_polygon(*trunk, fill="", outline="#553522", width=4)
        self.canvas.create_text(14, 12, anchor="nw", text="나무 잎은 초록색, 몸통은 무작위로 섞은 10가지 갈색입니다. 나방은 모두 몸통 안에 있습니다.",
                                font=("맑은 고딕", 9), fill="#173c24")
        for i, moth in enumerate(self.moths):
            x, y = self.position(i)
            self.draw_moth(x, y, moth, i)
        if self.parents:
            self.canvas.create_text(755, 425, anchor="nw", text="부모는 노란 테두리", font=("맑은 고딕", 8), fill="#685522")
        self.draw_graph()
        self.canvas.create_text(18, 25, anchor="nw", text="나방 날개 색 유전자 코드", font=("맑은 고딕", 8, "bold"), fill="#173c24")
        for i, color in enumerate(PALETTE):
            xx = 18+i*106
            self.canvas.create_rectangle(xx, 38, xx+14, 52, fill=hx(color), outline="#52634f")
            self.canvas.create_text(xx+18, 45, anchor="w", text=f"{i}: {COLOR_NAMES[i]}", font=("맑은 고딕", 8), fill="#263b2b")

    def close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    MothGA(window)
    window.mainloop()  # 10세대 완료 뒤에도 창과 최종 결과를 계속 표시

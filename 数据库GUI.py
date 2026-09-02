# -*- coding: utf-8 -*-
"""
SQLite 图形化管理工具（Windows GUI，独立运行）
================================================
- 完全独立：不依赖 数据库.py，可单独拷贝到任何位置直接运行
- 基于 tkinter（Python 自带），文件打开对话框使用 Windows 原生对话框
- 内置完整的 SQLite 核心（DatabaseManager + 文件校验），自动发现表
- 功能：打开/新建数据库、自动发现表、浏览数据、插入/修改/删除、条件查询

运行方式：
  python 数据库GUI.py            # 默认尝试打开 database.db
  python 数据库GUI.py 文件.db     # 启动时直接打开指定数据库

依赖：仅 Python 标准库（tkinter + sqlite3），无需安装第三方包。
"""

import os
import sqlite3
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ----------------------------------------------------------------------
# 内置核心：数据库文件校验
# ----------------------------------------------------------------------
DEFAULT_DB = "database.db"


def validate_sqlite(path):
    """
    校验一个文件是否为有效的 SQLite 数据库
    :param path: 文件路径
    :return: (是否有效, 说明信息)
    """
    try:
        size = os.path.getsize(path)
        # 空文件：SQLite 允许，首次写入时会自动初始化
        if size == 0:
            return True, "空文件，可当作新数据库使用"
        # 检查文件头：SQLite 数据库的前 16 字节固定为 "SQLite format 3\0"
        with open(path, "rb") as f:
            header = f.read(16)
        if header != b"SQLite format 3\x00":
            return False, f"'{path}' 不是有效的 SQLite 数据库（文件头不匹配）"
        # 实际打开并读取一次，排除损坏或加密的数据库
        conn = sqlite3.connect(path)
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
        conn.close()
        return True, "校验通过"
    except sqlite3.DatabaseError as e:
        return False, f"'{path}' 无法作为 SQLite 数据库打开: {e}"
    except OSError as e:
        return False, f"无法读取文件 '{path}': {e}"


# ----------------------------------------------------------------------
# 内置核心：SQLite 数据库管理器（自动发现表、增删改查）
# ----------------------------------------------------------------------
class DatabaseManager:
    """SQLite 数据库管理器（自动发现表）"""

    def __init__(self, db_path=DEFAULT_DB):
        """
        初始化：连接数据库（文件不存在时会自动创建）
        :param db_path: 数据库文件路径
        """
        self.db_path = db_path
        # connect 会自动创建不存在的数据库文件
        self.conn = sqlite3.connect(db_path)
        # 让查询结果可以按列名访问（如 row['name']）
        self.conn.row_factory = sqlite3.Row
        # 开启外键约束支持
        self.conn.execute("PRAGMA foreign_keys = ON")
        print(f"[OK] 已连接数据库: {db_path}")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            print("[OK] 数据库连接已关闭")

    # ------------------------------------------------------------------
    # 自动发现表 / 表结构
    # ------------------------------------------------------------------
    def list_tables(self):
        """
        自动发现数据库中所有用户数据表
        :return: 表名列表，如 ['user', 'ai_content']
        """
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        tables = [row[0] for row in self.conn.execute(sql).fetchall()]
        return tables

    def get_table_info(self, table_name):
        """
        读取表结构信息
        :param table_name: 表名
        :return: 列信息列表，每项为 dict：
                 {name: 列名, type: 类型, notnull: 是否非空, dflt: 默认值, pk: 是否主键(>0) }
        """
        # PRAGMA table_info 返回列: cid, name, type, notnull, dflt_value, pk
        rows = self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [
            {"name": r[1], "type": r[2], "notnull": r[3], "dflt": r[4], "pk": r[5]}
            for r in rows
        ]

    def get_primary_key(self, table_name):
        """
        获取表的主键列名（若无主键返回 None）
        :param table_name: 表名
        """
        for col in self.get_table_info(table_name):
            if col["pk"]:
                return col["name"]
        return None

    def show_table_info(self, table_name):
        """打印表结构"""
        print(f"--- 表 '{table_name}' 结构 ---")
        cols = self.get_table_info(table_name)
        for col in cols:
            parts = []
            if col["pk"]:
                parts.append("主键")
            if col["notnull"]:
                parts.append("NOT NULL")
            if col["dflt"] is not None:
                parts.append(f"默认={col['dflt']!r}")
            flags = "  " + ", ".join(parts) if parts else ""
            print(f"  {col['name']:<20} {col['type']:<12}{flags}")
        print(f"  记录数: {self.count(table_name)}")
        print()

    # ------------------------------------------------------------------
    # 建表（可选）
    # ------------------------------------------------------------------
    def create_table(self, table_name, columns_sql):
        """
        创建数据表（如果表已存在则跳过）
        :param table_name:  表名
        :param columns_sql: 列定义 SQL，例如 "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL"
        """
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_sql})"
        self.conn.execute(sql)
        self.conn.commit()
        print(f"[OK] 数据表 '{table_name}' 已就绪")

    # ------------------------------------------------------------------
    # 增（Insert）
    # ------------------------------------------------------------------
    def insert(self, table_name, data: dict):
        """
        插入一条记录
        :param table_name: 表名
        :param data: 字典，键为列名，值为要插入的值
                      例如 {"username": "张三", "age": 20}
        :return: 新插入记录的自增 id（若无自增主键则返回 None）
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        cur = self.conn.execute(sql, tuple(data.values()))
        self.conn.commit()
        print(f"[OK] 已插入 1 条记录到 '{table_name}'")
        return cur.lastrowid

    # ------------------------------------------------------------------
    # 查（Select）
    # ------------------------------------------------------------------
    def query(self, table_name, condition=None, params=(), columns="*", limit=None):
        """
        查询记录
        :param table_name: 表名
        :param condition:  条件子句，例如 "age > ? AND name LIKE ?"，None 表示查询全部
        :param params:     与条件中 ? 对应的参数元组
        :param columns:    要查询的列，默认 "*"
        :param limit:      最多返回的记录数，None 表示不限制
        :return: 查询到的记录列表（每行为 dict）
        """
        sql = f"SELECT {columns} FROM {table_name}"
        if condition:
            sql += f" WHERE {condition}"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        rows = self.conn.execute(sql, params).fetchall()
        print(f"[OK] 查询到 {len(rows)} 条记录")
        return [dict(row) for row in rows]

    def query_all(self, table_name):
        """查询表中的全部记录"""
        return self.query(table_name)

    # ------------------------------------------------------------------
    # 改（Update）
    # ------------------------------------------------------------------
    def update(self, table_name, data: dict, condition, params=()):
        """
        按条件修改记录
        :param table_name: 表名
        :param data: 字典，要修改的列及新值，例如 {"age": 21}
        :param condition: 条件子句，例如 "id = ?"
        :param params: 条件中 ? 对应的参数
        :return: 受影响的行数
        """
        set_clause = ", ".join([f"{col} = ?" for col in data.keys()])
        sql = f"UPDATE {table_name} SET {set_clause} WHERE {condition}"
        cur = self.conn.execute(sql, tuple(data.values()) + tuple(params))
        self.conn.commit()
        print(f"[OK] 已修改 {cur.rowcount} 条记录")
        return cur.rowcount

    # ------------------------------------------------------------------
    # 删（Delete）
    # ------------------------------------------------------------------
    def delete(self, table_name, condition, params=()):
        """
        按条件删除记录
        :param table_name: 表名
        :param condition: 条件子句，例如 "id = ?"
        :param params: 条件中 ? 对应的参数
        :return: 受影响的行数
        """
        sql = f"DELETE FROM {table_name} WHERE {condition}"
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        print(f"[OK] 已删除 {cur.rowcount} 条记录")
        return cur.rowcount

    def delete_all(self, table_name):
        """清空表中所有数据"""
        return self.delete(table_name, "1=1")

    def count(self, table_name, condition=None, params=()):
        """统计记录条数"""
        sql = f"SELECT COUNT(*) AS cnt FROM {table_name}"
        if condition:
            sql += f" WHERE {condition}"
        row = self.conn.execute(sql, params).fetchone()
        return row["cnt"]


def convert_value(raw, colinfo):
    """根据列类型把字符串转换为合适类型的值（int/float/str/None）"""
    raw = (raw or "").strip()
    if raw == "":
        return None
    typ = (colinfo["type"] or "TEXT").upper()
    if "INT" in typ:
        return int(raw)
    if any(x in typ for x in ("REAL", "FLOA", "DOUB", "NUM", "DEC")):
        return float(raw)
    return raw


class SqliteGuiApp:
    """SQLite 图形化主窗口"""

    def __init__(self, root, start_db=None):
        self.root = root
        self.db = None                       # DatabaseManager 实例
        self.current_table = None            # 当前选中的表
        self.table_cols = []                 # 当前表的列信息

        self._build_ui()
        self._set_status("请打开一个数据库文件")

        # 启动时自动打开指定（或默认）数据库
        target = start_db or DEFAULT_DB
        if os.path.exists(target):
            self.open_database(target, silent=True)

    # ==================================================================
    # 界面构建
    # ==================================================================
    def _build_ui(self):
        self.root.title("SQLite 数据库管理工具")
        self.root.geometry("1000x620")
        self.root.minsize(760, 480)

        # ---- 顶部：数据库文件栏 ----
        top = ttk.Frame(self.root, padding=(8, 6))
        top.pack(fill="x")
        ttk.Label(top, text="数据库文件:").pack(side="left")
        self.db_path_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.db_path_var, state="readonly").pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="打开…", command=self.ask_open_database).pack(side="left", padx=2)
        ttk.Button(top, text="新建…", command=self.ask_new_database).pack(side="left", padx=2)
        ttk.Button(top, text="关闭", command=self.close_database).pack(side="left", padx=2)

        # ---- 中部：左侧表列表 + 右侧数据区 ----
        main = ttk.Panedwindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # 左侧：数据表列表
        left = ttk.Frame(main, padding=4)
        main.add(left, weight=1)
        ttk.Label(left, text="数据表（双击查看结构）").pack(anchor="w")
        self.tables_tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.tables_tree.pack(side="left", fill="both", expand=True)
        tsv = ttk.Scrollbar(left, orient="vertical", command=self.tables_tree.yview)
        tsv.pack(side="right", fill="y")
        self.tables_tree.configure(yscrollcommand=tsv.set)
        self.tables_tree.bind("<<TreeviewSelect>>", self.on_table_selected)
        self.tables_tree.bind("<Double-1>", self.show_table_structure)

        # 右侧：数据浏览区
        right = ttk.Frame(main, padding=4)
        main.add(right, weight=4)

        # 操作按钮行
        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=(0, 4))
        ttk.Button(btns, text="插入记录", command=self.insert_record).pack(side="left", padx=2)
        ttk.Button(btns, text="修改记录", command=self.update_record).pack(side="left", padx=2)
        ttk.Button(btns, text="删除记录", command=self.delete_record).pack(side="left", padx=2)
        ttk.Button(btns, text="刷新", command=self.refresh_current_table).pack(side="left", padx=2)
        ttk.Button(btns, text="清空表", command=self.clear_current_table).pack(side="left", padx=2)

        # 条件查询行
        qf = ttk.Frame(right)
        qf.pack(fill="x", pady=(0, 4))
        ttk.Label(qf, text="WHERE 条件:").pack(side="left")
        self.query_var = tk.StringVar()
        ttk.Entry(qf, textvariable=self.query_var, width=40).pack(side="left", padx=4)
        ttk.Button(qf, text="查询", command=self.query_records).pack(side="left", padx=2)
        ttk.Button(qf, text="显示全部", command=self.refresh_current_table).pack(side="left", padx=2)

        # 数据表格
        data_frame = ttk.Frame(right)
        data_frame.pack(fill="both", expand=True)
        self.data_tree = ttk.Treeview(data_frame, show="headings", selectmode="browse")
        vs = ttk.Scrollbar(data_frame, orient="vertical", command=self.data_tree.yview)
        hs = ttk.Scrollbar(data_frame, orient="horizontal", command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.data_tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        data_frame.rowconfigure(0, weight=1)
        data_frame.columnconfigure(0, weight=1)

        # ---- 底部状态栏 ----
        self.status_var = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                  anchor="w", padding=(6, 2)).pack(fill="x", side="bottom")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ==================================================================
    # 数据库打开 / 关闭 / 新建
    # ==================================================================
    def ask_open_database(self):
        """使用 Windows 原生文件对话框选择数据库"""
        path = filedialog.askopenfilename(
            title="选择 SQLite 数据库",
            filetypes=[("SQLite 数据库", "*.db *.sqlite *.sqlite3 *.db3"),
                       ("所有文件", "*.*")],
        )
        if path:
            self.open_database(path)

    def open_database(self, path, silent=False):
        """打开数据库（带校验），失败时提示"""
        try:
            ok, msg = validate_sqlite(path)
            if not ok:
                if not silent:
                    messagebox.showerror("打开失败", msg, parent=self.root)
                self._set_status(msg)
                return
        except Exception as e:
            if not silent:
                messagebox.showerror("打开失败", str(e), parent=self.root)
            return

        self.close_database()
        try:
            self.db = DatabaseManager(path)
        except Exception as e:
            messagebox.showerror("打开失败", f"无法连接数据库:\n{e}", parent=self.root)
            return
        self.db_path_var.set(os.path.abspath(path))
        self._set_status(f"已打开: {path}")
        self._refresh_tables()

    def ask_new_database(self):
        """新建数据库文件"""
        path = filedialog.asksaveasfilename(
            title="新建数据库",
            defaultextension=".db",
            filetypes=[("SQLite 数据库", "*.db"), ("所有文件", "*.*")],
        )
        if not path:
            return
        if os.path.exists(path):
            if not messagebox.askyesno("确认", f"文件已存在，是否覆盖？\n{path}", parent=self.root):
                return
        try:
            # 创建空的 SQLite 文件（SQLite 会在首次写入时初始化）
            conn = sqlite3_connect_for_new(path)
            conn.close()
        except Exception as e:
            messagebox.showerror("新建失败", str(e), parent=self.root)
            return
        self.open_database(path)

    def close_database(self):
        if self.db:
            self.db.close()
            self.db = None
        self.current_table = None
        self.table_cols = []
        self.db_path_var.set("")
        self.tables_tree.delete(*self.tables_tree.get_children())
        self._clear_data_grid()
        self._set_status("数据库已关闭")

    # ==================================================================
    # 表列表 / 数据加载
    # ==================================================================
    def _refresh_tables(self):
        self.tables_tree.delete(*self.tables_tree.get_children())
        if not self.db:
            return
        for t in self.db.list_tables():
            try:
                cnt = self.db.count(t)
            except Exception:
                cnt = "?"
            self.tables_tree.insert("", "end", iid=t, text=f"{t}  ({cnt} 条)")
        # 默认选中第一张表
        children = self.tables_tree.get_children()
        if children:
            self.tables_tree.selection_set(children[0])
            self.on_table_selected()

    def on_table_selected(self, _event=None):
        sel = self.tables_tree.selection()
        if not sel:
            return
        self.current_table = sel[0]
        self.table_cols = self.db.get_table_info(self.current_table)
        self._set_status(f"当前表: {self.current_table}")
        self.refresh_current_table()

    def refresh_current_table(self):
        if not self.current_table:
            return
        self.load_data()

    def load_data(self, condition=None, params=()):
        """按条件加载数据到表格"""
        self._clear_data_grid()
        if not self.current_table:
            return
        try:
            rows = self.db.query(self.current_table, condition, params)
        except Exception as e:
            messagebox.showerror("查询失败", str(e), parent=self.root)
            return

        cols = list(rows[0].keys()) if rows else [c["name"] for c in self.table_cols]
        self.data_tree["columns"] = cols
        for c in cols:
            self.data_tree.heading(c, text=c)
            self.data_tree.column(c, width=140, anchor="w", stretch=True)
        for row in rows:
            self.data_tree.insert("", "end", values=[row[c] for c in cols])

        self._set_status(f"表 '{self.current_table}': 共 {len(rows)} 条记录"
                         + (f"（条件: {condition}）" if condition else ""))

    def query_records(self):
        cond = self.query_var.get().strip()
        if not cond:
            self.refresh_current_table()
            return
        self.load_data(cond)

    def show_table_structure(self, _event=None):
        """双击表名：显示表结构"""
        if not self.current_table:
            return
        lines = [f"表: {self.current_table}"]
        for c in self.table_cols:
            parts = [c["name"], c["type"] or ""]
            if c["pk"]:
                parts.append("主键")
            if c["notnull"]:
                parts.append("NOT NULL")
            if c["dflt"] is not None:
                parts.append(f"默认={c['dflt']!r}")
            lines.append("  " + ", ".join(parts))
        messagebox.showinfo("表结构", "\n".join(lines), parent=self.root)

    # ==================================================================
    # 增 / 改 / 删
    # ==================================================================
    def _pk_columns(self):
        return [c for c in self.table_cols if c["pk"]]

    def insert_record(self):
        if not self.current_table:
            messagebox.showwarning("提示", "请先选择一张表", parent=self.root)
            return
        cols = self.table_cols
        # 跳过 INTEGER 自增主键（数据库自动生成）
        editable = [c for c in cols if not (c["pk"] and "INT" in (c["type"] or "").upper())]
        fields = [(c["name"], c) for c in editable]
        values = self._prompt_values(f"插入记录 - {self.current_table}", fields)
        if values is None:
            return
        # 必填校验
        missing = [c["name"] for c in editable
                   if c["notnull"] and (values.get(c["name"]) is None)]
        if missing:
            messagebox.showwarning("输入不完整",
                                   "以下必填列未填写:\n" + ", ".join(missing), parent=self.root)
            return
        data = {k: v for k, v in values.items() if v is not None}
        try:
            self.db.insert(self.current_table, data)
        except Exception as e:
            messagebox.showerror("插入失败", str(e), parent=self.root)
            return
        self.refresh_current_table()
        self._refresh_tables()   # 更新左侧记录数

    def update_record(self):
        if not self.current_table:
            messagebox.showwarning("提示", "请先选择一张表", parent=self.root)
            return
        sel = self.data_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先在数据区选择一行", parent=self.root)
            return
        cols = self.table_cols
        col_names = [c["name"] for c in cols]
        row_vals = self.data_tree.item(sel[0], "values")

        pks = self._pk_columns() or [cols[0]]
        cond_col = pks[0]["name"]
        cond_val = row_vals[col_names.index(cond_col)]

        # 可修改列 = 除主键外的所有列
        editable = [c for c in cols if not c["pk"]]
        fields = []
        defaults = {}
        for c in editable:
            idx = col_names.index(c["name"])
            defaults[c["name"]] = row_vals[idx]
            fields.append((c["name"], c))
        values = self._prompt_values(f"修改记录（{cond_col}={cond_val}）", fields, defaults)
        if values is None:
            return
        data = {k: v for k, v in values.items() if v is not None}
        if not data:
            return
        try:
            self.db.update(self.current_table, data, f"{cond_col} = ?", (cond_val,))
        except Exception as e:
            messagebox.showerror("修改失败", str(e), parent=self.root)
            return
        self.refresh_current_table()

    def delete_record(self):
        if not self.current_table:
            messagebox.showwarning("提示", "请先选择一张表", parent=self.root)
            return
        sel = self.data_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先在数据区选择一行", parent=self.root)
            return
        cols = self.table_cols
        col_names = [c["name"] for c in cols]
        row_vals = self.data_tree.item(sel[0], "values")
        pks = self._pk_columns() or [cols[0]]
        cond_col = pks[0]["name"]
        cond_val = row_vals[col_names.index(cond_col)]
        if not messagebox.askyesno("确认删除",
                                   f"确定删除 {cond_col}={cond_val} 的记录吗？", parent=self.root):
            return
        try:
            self.db.delete(self.current_table, f"{cond_col} = ?", (cond_val,))
        except Exception as e:
            messagebox.showerror("删除失败", str(e), parent=self.root)
            return
        self.refresh_current_table()
        self._refresh_tables()

    def clear_current_table(self):
        if not self.current_table:
            return
        if not messagebox.askyesno("清空表",
                                   f"确定清空表 '{self.current_table}' 的所有记录吗？",
                                   parent=self.root):
            return
        self.db.delete_all(self.current_table)
        self.refresh_current_table()
        self._refresh_tables()

    # ==================================================================
    # 通用表单对话框
    # ==================================================================
    def _prompt_values(self, title, fields, defaults=None):
        """
        弹出表单窗口，按列提示输入
        :param fields: [(列名, 列信息dict), ...]
        :param defaults: {列名: 默认值}，修改时使用
        :return: {列名: 转换后的值}；用户取消返回 None
        """
        defaults = defaults or {}
        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        result = {}

        vars_ = {}
        for i, (name, colinfo) in enumerate(fields):
            ttk.Label(win, text=name).grid(row=i, column=0, sticky="e", padx=8, pady=3)
            var = tk.StringVar(value=str(defaults.get(name, "")) if defaults.get(name, "") is not None else "")
            vars_[name] = (var, colinfo)
            ttk.Entry(win, textvariable=var, width=46).grid(row=i, column=1, sticky="we", padx=8, pady=3)

        def on_ok():
            try:
                for name, (var, colinfo) in vars_.items():
                    result[name] = convert_value(var.get(), colinfo)
            except ValueError as e:
                messagebox.showerror("输入错误", str(e), parent=win)
                return
            win.destroy()

        def on_cancel():
            win.destroy()

        btns = ttk.Frame(win)
        btns.grid(row=len(fields), column=0, columnspan=2, pady=10)
        ttk.Button(btns, text="确定", command=on_ok).pack(side="left", padx=8)
        ttk.Button(btns, text="取消", command=on_cancel).pack(side="left", padx=8)

        win.bind("<Return>", lambda e: on_ok())
        win.bind("<Escape>", lambda e: on_cancel())
        win.wait_window()
        return result if result else None

    # ==================================================================
    # 其他
    # ==================================================================
    def _clear_data_grid(self):
        self.data_tree.delete(*self.data_tree.get_children())
        self.data_tree["columns"] = ()

    def _set_status(self, msg):
        self.status_var.set(msg)

    def on_close(self):
        self.close_database()
        self.root.destroy()


def sqlite3_connect_for_new(path):
    """新建数据库：直接使用 sqlite3 连接创建空文件"""
    import sqlite3
    return sqlite3.connect(path)


def main():
    root = tk.Tk()
    start_db = sys.argv[1] if len(sys.argv) > 1 else None
    SqliteGuiApp(root, start_db)
    root.mainloop()


if __name__ == "__main__":
    main()

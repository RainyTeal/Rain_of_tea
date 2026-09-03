"""

运行方式：
  python 数据库.py               # 启动后提示输入数据库文件路径（带校验）
  python 数据库.py 文件名.db      # 直接指定数据库文件（同样会校验）
  python 数据库.py demo          # 只读演示：自动发现并展示表结构与数据

"""

import os
import sqlite3
import sys

# 让中文输出在控制台正常显示（UTF-8）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 默认数据库文件名
DEFAULT_DB = "database.db"


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


# ----------------------------------------------------------------------
# 交互式命令行菜单
# ----------------------------------------------------------------------
def input_value(col):
    """根据列信息提示用户输入一个值"""
    name, typ = col["name"], col["type"].upper()
    while True:
        raw = input(f"  请输入 {name} ({typ}){'(必填)' if col['notnull'] else ''}: ").strip()
        if raw == "" and not col["notnull"]:
            return None
        if raw == "" and col["notnull"]:
            print("    [该列不能为空，请重新输入]")
            continue
        try:
            if "INT" in typ:
                return int(raw)
            if "REAL" in typ or "FLOA" in typ or "DOUB" in typ or "NUM" in typ or "DEC" in typ:
                return float(raw)
            return raw
        except ValueError:
            print(f"    [{typ} 类型，请输入有效数字]")


def choose_table(db):
    """列出所有表并让用户选择，返回表名"""
    tables = db.list_tables()
    if not tables:
        print("[!] 当前数据库中没有数据表")
        return None
    print("\n--- 数据库中的表 ---")
    for i, t in enumerate(tables, 1):
        try:
            cnt = db.count(t)
        except Exception:
            cnt = "?"
        print(f"  {i}. {t}  ({cnt} 条记录)")
    while True:
        choice = input("请选择表编号（或输入表名）: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(tables):
            return tables[int(choice) - 1]
        if choice in tables:
            return choice
        print("[!] 无效选择，请重试")


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


def choose_db_file(default=DEFAULT_DB):
    """
    让用户在命令行输入数据库文件路径，并进行校验
    :param default: 默认文件路径（直接回车时使用）
    :return: 通过校验（或确认创建）的文件路径
    """
    print("需要打开或创建哪一个 SQLite 数据库文件？")
    print(f"（直接回车使用默认值: {default}）")
    while True:
        raw = input("请输入数据库文件路径: ").strip().strip("'\"")
        path = os.path.expanduser(raw) if raw else default

        # 校验 1：扩展名必须是 .db（也接受 .sqlite / .sqlite3 / .db3）
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".db", ".sqlite", ".sqlite3", ".db3"):
            print("[!] 路径应以 .db / .sqlite / .sqlite3 / .db3 结尾")
            continue

        # 校验 2：文件是否已存在
        if not os.path.exists(path):
            ans = input(f"[!] 文件 '{path}' 不存在，是否创建新的数据库？(y/n): ").strip().lower()
            if ans in ("y", "yes"):
                return path
            print("请重新输入路径")
            continue

        # 校验 3：是否为有效的 SQLite 数据库
        ok, msg = validate_sqlite(path)
        if not ok:
            print(f"[!] {msg}")
            continue
        return path


def interactive_menu(db_path):
    """命令行交互式增删改查菜单（自动发现表）"""
    db = DatabaseManager(db_path)
    table = choose_table(db)
    if table is None:
        db.close()
        return

    while True:
        menu = f"""
=============== SQLite 增删改查菜单 ===============
  数据库: {db.db_path}    当前表: {table}
  1. 切换数据表          2. 查看表结构
  3. 插入记录（增）      4. 查询全部（查）
  5. 条件查询（查）      6. 修改记录（改）
  7. 删除记录（删）      8. 清空所有记录
  9. 统计记录条数        0. 退出
=================================================="""
        print(menu)
        choice = input("请选择操作 [0-9]: ").strip()

        try:
            if choice == "1":            # 切换表
                new_table = choose_table(db)
                if new_table:
                    table = new_table

            elif choice == "2":          # 查看结构
                db.show_table_info(table)

            elif choice == "3":          # 增
                cols = db.get_table_info(table)
                data = {}
                for col in cols:
                    if col["pk"] and "INT" in col["type"].upper():
                        # 跳过 INTEGER 自增主键（由数据库自动生成）
                        continue
                    val = input_value(col)
                    if val is not None:
                        data[col["name"]] = val
                if data:
                    db.insert(table, data)

            elif choice == "4":          # 查全部
                rows = db.query_all(table)
                print_rows(rows)

            elif choice == "5":          # 条件查询
                print("示例条件: id > 10 AND role = 'admin'（列名用英文原列名）")
                cond = input("请输入 WHERE 条件（空则查询全部）: ").strip()
                if cond:
                    rows = db.query(table, cond)
                else:
                    rows = db.query_all(table)
                print_rows(rows)

            elif choice == "6":          # 改
                print("--- 请先指定要修改哪条记录 ---")
                cols = db.get_table_info(table)
                pk = db.get_primary_key(table)
                # 条件：优先用主键，否则用第一个列
                cond_col = pk if pk else cols[0]["name"]
                cond_val = input(f"  输入要修改记录的 {cond_col} 值: ").strip()
                if not cond_val:
                    print("[!] 已取消")
                    continue
                # 根据列类型转换条件值
                cond_type = next((c for c in cols if c["name"] == cond_col), None)
                if cond_type and "INT" in cond_type["type"].upper():
                    cond_val = int(cond_val)

                # 选择要修改的列
                print("--- 可修改的列 ---")
                for i, col in enumerate(cols, 1):
                    print(f"  {i}. {col['name']} ({col['type']})")
                col_idx = int(input("要修改哪一列（输入编号）: ").strip())
                col = cols[col_idx - 1]
                new_val = input_value(col)
                if new_val is not None:
                    db.update(table, {col["name"]: new_val}, f"{cond_col} = ?", (cond_val,))

            elif choice == "7":          # 删
                print("--- 删除记录 ---")
                cols = db.get_table_info(table)
                pk = db.get_primary_key(table)
                cond_col = pk if pk else cols[0]["name"]
                print(f"按 {cond_col} 删除（也可输入完整 WHERE 条件）")
                val = input(f"  输入要删除的 {cond_col}（多个用逗号分隔）: ").strip()
                if not val:
                    print("[!] 已取消")
                    continue
                cond_type = next((c for c in cols if c["name"] == cond_col), None)
                for v in val.split(","):
                    v = v.strip()
                    if not v:
                        continue
                    if cond_type and "INT" in cond_type["type"].upper():
                        v = int(v)
                    db.delete(table, f"{cond_col} = ?", (v,))

            elif choice == "8":          # 清空
                confirm = input("确认清空所有记录？输入 yes 确认: ").strip()
                if confirm.lower() == "yes":
                    db.delete_all(table)

            elif choice == "9":          # 统计
                print(f"[OK] 表 '{table}' 共有 {db.count(table)} 条记录")

            elif choice == "0":
                break

            else:
                print("[!] 无效选项，请重新输入")
        except Exception as e:
            print(f"[!] 操作失败: {e}")

    db.close()


def print_rows(rows):
    """以表格形式打印查询结果"""
    if not rows:
        print("（无记录）")
        return
    keys = list(rows[0].keys())
    header = " | ".join(str(k) for k in keys)
    print("-" * (len(header) + 4))
    print(" " + header)
    print("-" * (len(header) + 4))
    for row in rows:
        print(" " + " | ".join(str(row[k]) for k in keys))
    print("-" * (len(header) + 4))


# ----------------------------------------------------------------------
# 只读演示（python 数据库.py demo）
# ----------------------------------------------------------------------
def run_demo(db_path):
    """自动发现表并展示结构、记录数、示例数据（只读，不修改任何数据）"""
    print("============ 开始演示（只读） ============")
    db = DatabaseManager(db_path)

    tables = db.list_tables()
    print(f"[OK] 自动发现 {len(tables)} 张表: {tables}\n")

    if not tables:
        print("[!] 该数据库中没有数据表")
        db.close()
        return

    for t in tables:
        # 1. 展示表结构
        db.show_table_info(t)
        # 2. 示例数据（最多 3 条）
        print(f"--- 表 '{t}' 示例数据（最多 3 条）---")
        rows = db.query(t, limit=3)
        print_rows(rows)
        print()

    # 3. 如果有表，演示一次条件查询（选第一张表）
    first = tables[0]
    pk = db.get_primary_key(first)
    if pk:
        print(f"--- 条件查询演示: {first} WHERE {pk} >= ? ---")
        rows = db.query(first, f"{pk} >= ?", (1,), limit=5)
        print_rows(rows)
    print("============ 演示结束（未修改任何数据） ============")
    db.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "demo":
        db_file = args[1] if len(args) > 1 else DEFAULT_DB
        run_demo(db_file)
    elif args:
        # 支持: python 数据库.py 任意.db（同样做校验，不通过则回到交互选择）
        path = os.path.expanduser(args[0])
        if not os.path.exists(path):
            print(f"[!] 文件 '{path}' 不存在")
            interactive_menu(choose_db_file())
        else:
            ok, msg = validate_sqlite(path)
            if not ok:
                print(f"[!] {msg}")
                interactive_menu(choose_db_file())
            else:
                interactive_menu(path)
    else:
        # 无参数：启动时让用户输入文件路径
        interactive_menu(choose_db_file())

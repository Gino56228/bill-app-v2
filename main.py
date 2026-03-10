import json
import os
import re
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.switch import Switch
from kivy.clock import Clock
from kivy.utils import platform
from kivy.storage.jsonstore import JsonStore

# ================== 基础配置 ==================
# 使用Kivy的JsonStore，自动处理路径问题
# Android: /data/data/org.test.myapp/files/app/bill_data.json
# Desktop: 当前目录
BILL_FILE = "bill_data.json"
CONFIG_FILE = "bill_config.json"

# 记账分类
CATEGORIES = ["餐饮", "交通", "购物", "娱乐", "日用", "医疗", "住房", "通讯", "其他"]

# ================== 数据存储 ==================
class DataManager:
    """数据管理器，处理跨平台存储"""
    def __init__(self):
        self.bill_store = JsonStore(BILL_FILE)
        self.config_store = JsonStore(CONFIG_FILE)

    def load_bills(self):
        """加载账单数据"""
        bills = []
        if self.bill_store.exists('bills'):
            bills = self.bill_store.get('bills')['data']
        return bills

    def save_bills(self, bills):
        """保存账单数据"""
        self.bill_store.put('bills', data=bills)

    def load_config(self):
        """加载配置"""
        default_config = {"password": "123456", "dark_mode": False}
        if self.config_store.exists('config'):
            return self.config_store.get('config')
        return default_config

    def save_config(self, config):
        """保存配置"""
        self.config_store.put('config', **config)

# 全局数据管理器
data_manager = DataManager()

def load_bills():
    return data_manager.load_bills()

def save_bills(bills):
    data_manager.save_bills(bills)

def load_config():
    return data_manager.load_config()

def save_config(config):
    data_manager.save_config(config)

# ================== 工具函数 ==================
def extract_money(text):
    """从语音文本中提取金额"""
    # 支持中文数字转换
    chinese_nums = {
        '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '百': 100, '千': 1000, '万': 10000
    }

    # 先尝试匹配阿拉伯数字
    match = re.search(r'(\d+\.?\d*)', text)
    if match:
        return float(match.group(1))

    # 尝试匹配中文数字（简化版）
    total = 0
    current = 0
    for char in text:
        if char in chinese_nums:
            num = chinese_nums[char]
            if num >= 10:
                if current == 0:
                    current = 1
                total += current * num
                current = 0
            else:
                current = current * 10 + num if current else num
    total += current
    return float(total) if total > 0 else 0.0

def speech_recognize():
    """安卓原生语音识别"""
    if platform != 'android':
        return "⚠️ 仅安卓支持语音"

    try:
        from jnius import autoclass, cast
        from android import activity

        Intent = autoclass("android.content.Intent")
        RecognizerIntent = autoclass("android.speech.RecognizerIntent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, 
                       RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "请说出消费金额和用途")

        current_activity = PythonActivity.mActivity

        def on_result(request_code, result_code, data):
            if request_code == 100 and result_code == -1:  # RESULT_OK = -1
                try:
                    ArrayList = autoclass("java.util.ArrayList")
                    results = data.getStringArrayListExtra(
                        RecognizerIntent.EXTRA_RESULTS
                    )
                    if results and results.size() > 0:
                        text = results.get(0)
                        # 使用Clock在主线程更新UI
                        Clock.schedule_once(
                            lambda dt: App.get_running_app().ui.on_voice_result(text), 0
                        )
                except Exception as e:
                    print(f"语音识别结果处理错误: {e}")
                    Clock.schedule_once(
                        lambda dt: TipPopup("❌ 语音识别失败").open(), 0
                    )

        activity.bind(on_activity_result=on_result)
        current_activity.startActivityForResult(intent, 100)
        return "🎤 请说话..."
    except Exception as e:
        print(f"语音识别启动错误: {e}")
        return f"⚠️ 语音功能错误: {str(e)}"

def export_csv():
    """导出CSV（跨平台兼容）"""
    try:
        import csv
        from kivy.storage.jsonstore import JsonStore
        from os.path import join, expanduser

        # 获取导出路径
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.WRITE_EXTERNAL_STORAGE])

            # Android共享目录
            path = "/sdcard/Download/记账记录.csv"
        else:
            path = join(expanduser("~"), "Desktop", "记账记录.csv")

        bills = load_bills()
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["时间", "分类", "金额", "备注"])
            for bill in bills:
                writer.writerow([
                    bill.get("time", ""),
                    bill.get("category", ""),
                    bill.get("amount", 0),
                    bill.get("note", "")
                ])
        return f"✅ 导出成功: {path}"
    except Exception as e:
        return f"❌ 导出失败: {str(e)}"

# ================== 弹窗组件 ==================
class TipPopup(Popup):
    """提示弹窗"""
    def __init__(self, message, **kwargs):
        super().__init__(title="提示", size_hint=(0.8, 0.25), auto_dismiss=True)
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content.add_widget(Label(text=message, text_size=(None, None)))

        btn = Button(text="确定", size_hint_y=None, height=40)
        btn.bind(on_press=self.dismiss)
        content.add_widget(btn)

        self.add_widget(content)

class PasswordPopup(Popup):
    """密码验证弹窗"""
    def __init__(self, callback, **kwargs):
        super().__init__(title="请输入密码", size_hint=(0.85, 0.4), auto_dismiss=False)
        self.callback = callback
        layout = BoxLayout(orientation="vertical", spacing=10, padding=15)

        self.pwd_input = TextInput(
            hint_text="默认密码：123456", 
            password=True,
            multiline=False,
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.pwd_input)

        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)

        confirm_btn = Button(text="确认")
        confirm_btn.bind(on_press=self.check_password)
        btn_layout.add_widget(confirm_btn)

        exit_btn = Button(text="退出")
        exit_btn.bind(on_press=lambda x: callback(False))
        btn_layout.add_widget(exit_btn)

        layout.add_widget(btn_layout)
        self.add_widget(layout)

        # 绑定回车键
        self.pwd_input.bind(on_text_validate=self.check_password)

    def check_password(self, *args):
        config = load_config()
        if self.pwd_input.text == config.get("password", "123456"):
            self.callback(True)
            self.dismiss()
        else:
            self.pwd_input.text = ""
            TipPopup("❌ 密码错误").open()

class CategoryPopup(Popup):
    """分类选择弹窗"""
    def __init__(self, callback, **kwargs):
        super().__init__(title="选择消费分类", size_hint=(0.85, 0.8))
        layout = BoxLayout(orientation="vertical", spacing=5, padding=10)

        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=8, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for cate in CATEGORIES:
            btn = Button(text=cate, size_hint_y=None, height=55)
            btn.bind(on_press=lambda x, c=cate: self.select_category(c, callback))
            grid.add_widget(btn)

        scroll.add_widget(grid)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def select_category(self, category, callback):
        callback(category)
        self.dismiss()

class ManualInputPopup(Popup):
    """手动输入弹窗（语音失败时使用）"""
    def __init__(self, callback, **kwargs):
        super().__init__(title="手动记账", size_hint=(0.85, 0.5))
        self.callback = callback

        layout = BoxLayout(orientation="vertical", spacing=10, padding=15)

        self.amount_input = TextInput(
            hint_text="金额（如：25.5）",
            input_filter="float",
            multiline=False,
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.amount_input)

        self.note_input = TextInput(
            hint_text="备注（如：午餐）",
            multiline=False,
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.note_input)

        btn = Button(text="下一步", size_hint_y=None, height=50)
        btn.bind(on_press=self.on_confirm)
        layout.add_widget(btn)

        self.add_widget(layout)
        self.amount_input.bind(on_text_validate=lambda x: self.note_input.focus)
        self.note_input.bind(on_text_validate=self.on_confirm)

    def on_confirm(self, *args):
        try:
            amount = float(self.amount_input.text or 0)
            if amount <= 0:
                TipPopup("❌ 请输入有效金额").open()
                return
            self.dismiss()
            self.callback(amount, self.note_input.text or "手动记账")
        except ValueError:
            TipPopup("❌ 金额格式错误").open()

# ================== 主界面 ==================
class BillAppUI(BoxLayout):
    """主界面布局"""
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=15, spacing=10)
        self.config = load_config()
        self.current_note = ""
        self.current_amount = 0.0

        # 标题
        title = Label(
            text="📝 简易语音记账", 
            font_size=24, 
            size_hint_y=0.08,
            bold=True
        )
        self.add_widget(title)

        # 统计信息
        self.stats_label = Label(
            text="", 
            font_size=14, 
            size_hint_y=0.06,
            color=(0.3, 0.6, 1, 1)
        )
        self.add_widget(self.stats_label)

        # 功能按钮行
        btn_layout = BoxLayout(size_hint_y=0.1, spacing=8)

        voice_btn = Button(text="🎤 语音记账", font_size=16)
        voice_btn.bind(on_press=self.start_voice)
        btn_layout.add_widget(voice_btn)

        manual_btn = Button(text="✏️ 手动记账", font_size=16)
        manual_btn.bind(on_press=self.start_manual)
        btn_layout.add_widget(manual_btn)

        list_btn = Button(text="📜 查看账单", font_size=16)
        list_btn.bind(on_press=self.show_bills)
        btn_layout.add_widget(list_btn)

        setting_btn = Button(text="⚙️ 设置", font_size=16)
        setting_btn.bind(on_press=self.show_settings)
        btn_layout.add_widget(setting_btn)

        self.add_widget(btn_layout)

        # 账单列表区域
        self.scroll_view = ScrollView()
        self.bill_list = GridLayout(cols=1, size_hint_y=None, spacing=10)
        self.bill_list.bind(minimum_height=self.bill_list.setter("height"))
        self.scroll_view.add_widget(self.bill_list)
        self.add_widget(self.scroll_view)

        # 初始化加载账单
        self.show_bills(None)
        self.update_stats()

    def update_stats(self):
        """更新统计信息"""
        bills = load_bills()
        total = sum(bill.get("amount", 0) for bill in bills)
        today = datetime.now().strftime("%Y-%m-%d")
        today_total = sum(
            bill.get("amount", 0) for bill in bills 
            if bill.get("time", "").startswith(today)
        )
        self.stats_label.text = f"总支出: ¥{total:.2f}  |  今日: ¥{today_total:.2f}"

    def start_voice(self, *args):
        """启动语音识别"""
        tip = speech_recognize()
        if "⚠️" in tip:
            # 如果不支持语音，提供手动输入
            ManualInputPopup(self.on_manual_result).open()
        else:
            TipPopup(tip).open()

    def start_manual(self, *args):
        """启动手动输入"""
        ManualInputPopup(self.on_manual_result).open()

    def on_manual_result(self, amount, note):
        """处理手动输入结果"""
        self.current_amount = amount
        self.current_note = note
        CategoryPopup(self.save_bill).open()

    def on_voice_result(self, text):
        """处理语音识别结果"""
        self.current_amount = extract_money(text)
        self.current_note = text

        if self.current_amount <= 0:
            TipPopup(f"❌ 未识别到金额：{text}\n请使用手动记账").open()
            return

        # 选择分类
        CategoryPopup(self.save_bill).open()

    def save_bill(self, category):
        """保存账单"""
        bill = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "category": category,
            "amount": self.current_amount,
            "note": self.current_note
        }

        bills = load_bills()
        bills.insert(0, bill)  # 新账单插入到前面
        save_bills(bills)

        TipPopup(f"✅ 记账成功：{category} ¥{self.current_amount:.2f}").open()
        self.show_bills(None)
        self.update_stats()

    def show_bills(self, *args):
        """显示所有账单"""
        self.bill_list.clear_widgets()
        bills = load_bills()

        if not bills:
            label = Label(
                text="暂无账单记录\n点击🎤语音记账或✏️手动记账开始记录", 
                size_hint_y=None, 
                height=150,
                color=(0.5, 0.5, 0.5, 1)
            )
            self.bill_list.add_widget(label)
            return

        for i, bill in enumerate(bills):
            bill_item = BoxLayout(
                orientation="vertical", 
                size_hint_y=None, 
                height=100, 
                padding=10,
                spacing=2
            )

            # 背景色交替
            if i % 2 == 0:
                bill_item.canvas.before.clear()
                with bill_item.canvas.before:
                    from kivy.graphics import Color, Rectangle
                    Color(0.95, 0.95, 0.95, 1)
                    rect = Rectangle(pos=bill_item.pos, size=bill_item.size)
                    bill_item.bind(pos=lambda obj, val: setattr(rect, 'pos', val))
                    bill_item.bind(size=lambda obj, val: setattr(rect, 'size', val))

            time_text = bill.get('time', '未知时间')
            category_text = bill.get('category', '未分类')
            amount = bill.get('amount', 0)
            note_text = bill.get('note', '')

            top_layout = BoxLayout(size_hint_y=0.4)
            top_layout.add_widget(Label(
                text=f"{time_text}  |  {category_text}", 
                font_size=13,
                halign='left',
                text_size=(None, None)
            ))
            top_layout.add_widget(Label(
                text=f"¥{amount:.2f}", 
                font_size=18, 
                color=(1, 0.2, 0.2, 1),
                bold=True,
                halign='right',
                size_hint_x=0.4
            ))
            bill_item.add_widget(top_layout)

            if note_text:
                bill_item.add_widget(Label(
                    text=f"备注：{note_text}", 
                    font_size=12,
                    color=(0.4, 0.4, 0.4, 1),
                    halign='left',
                    text_size=(None, None),
                    size_hint_y=0.3
                ))

            self.bill_list.add_widget(bill_item)

    def show_settings(self, *args):
        """显示设置界面"""
        setting_popup = Popup(title="设置", size_hint=(0.85, 0.7))
        layout = BoxLayout(orientation="vertical", spacing=10, padding=15)

        # 暗黑模式开关
        dark_layout = BoxLayout(size_hint_y=None, height=50)
        dark_layout.add_widget(Label(text="暗黑模式：", font_size=16))
        dark_switch = Switch(active=self.config.get("dark_mode", False))
        dark_switch.bind(active=self.toggle_dark_mode)
        dark_layout.add_widget(dark_switch)
        layout.add_widget(dark_layout)

        # 导出CSV按钮
        export_btn = Button(
            text="📤 导出CSV文件", 
            size_hint_y=None, 
            height=55,
            font_size=16
        )
        export_btn.bind(on_press=lambda x: TipPopup(export_csv()).open())
        layout.add_widget(export_btn)

        # 清空数据按钮
        clear_btn = Button(
            text="🗑️ 清空所有账单", 
            size_hint_y=None, 
            height=55,
            font_size=16,
            background_color=(1, 0.3, 0.3, 1)
        )
        clear_btn.bind(on_press=self.confirm_clear)
        layout.add_widget(clear_btn)

        # 修改密码按钮
        pwd_btn = Button(
            text="🔒 修改密码", 
            size_hint_y=None, 
            height=55,
            font_size=16
        )
        pwd_btn.bind(on_press=self.change_password)
        layout.add_widget(pwd_btn)

        # 关于
        about_label = Label(
            text="简易语音记账 v1.0\n支持语音识别记账和手动记账",
            font_size=12,
            color=(0.5, 0.5, 0.5, 1),
            size_hint_y=None,
            height=60
        )
        layout.add_widget(about_label)

        setting_popup.add_widget(layout)
        setting_popup.open()

    def confirm_clear(self, *args):
        """确认清空数据"""
        popup = Popup(title="确认清空", size_hint=(0.8, 0.3))
        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        layout.add_widget(Label(text="确定要清空所有账单吗？\n此操作不可恢复！"))

        btn_layout = BoxLayout(spacing=10)

        yes_btn = Button(text="确定清空", background_color=(1, 0.2, 0.2, 1))
        yes_btn.bind(on_press=lambda x: [self.do_clear(), popup.dismiss()])
        btn_layout.add_widget(yes_btn)

        no_btn = Button(text="取消")
        no_btn.bind(on_press=popup.dismiss)
        btn_layout.add_widget(no_btn)

        layout.add_widget(btn_layout)
        popup.add_widget(layout)
        popup.open()

    def do_clear(self):
        """执行清空"""
        save_bills([])
        self.show_bills(None)
        self.update_stats()
        TipPopup("✅ 已清空所有账单").open()

    def toggle_dark_mode(self, instance, value):
        """切换暗黑模式"""
        self.config["dark_mode"] = value
        save_config(self.config)
        TipPopup("✅ 设置已保存，重启生效").open()

    def change_password(self, *args):
        """修改密码"""
        pwd_popup = Popup(title="修改密码", size_hint=(0.85, 0.5))
        layout = BoxLayout(orientation="vertical", spacing=10, padding=15)

        old_pwd = TextInput(
            hint_text="输入原密码", 
            password=True,
            multiline=False,
            size_hint_y=None,
            height=50
        )
        layout.add_widget(old_pwd)

        new_pwd1 = TextInput(
            hint_text="输入新密码", 
            password=True,
            multiline=False,
            size_hint_y=None,
            height=50
        )
        layout.add_widget(new_pwd1)

        new_pwd2 = TextInput(
            hint_text="确认新密码", 
            password=True,
            multiline=False,
            size_hint_y=None,
            height=50
        )
        layout.add_widget(new_pwd2)

        save_btn = Button(text="保存", size_hint_y=None, height=50)

        def save_pwd(*args):
            config = load_config()
            if old_pwd.text != config.get("password", "123456"):
                TipPopup("❌ 原密码错误").open()
                return
            if new_pwd1.text != new_pwd2.text:
                TipPopup("❌ 两次新密码不一致").open()
                return
            if len(new_pwd1.text) < 4:
                TipPopup("❌ 密码至少4位").open()
                return

            self.config["password"] = new_pwd1.text
            save_config(self.config)
            TipPopup("✅ 密码修改成功").open()
            pwd_popup.dismiss()

        save_btn.bind(on_press=save_pwd)
        layout.add_widget(save_btn)
        pwd_popup.add_widget(layout)
        pwd_popup.open()

# ================== APP入口 ==================
class BillApp(App):
    """APP主类"""
    def build(self):
        """构建APP"""
        self.title = "简易语音记账"
        self.ui = BillAppUI()

        # 延迟显示密码弹窗，确保UI加载完成
        Clock.schedule_once(lambda dt: PasswordPopup(self.on_password_verified).open(), 0.5)

        return self.ui

    def on_password_verified(self, verified):
        """密码验证回调"""
        if not verified:
            self.stop()

    def on_pause(self):
        """处理应用暂停（Android返回桌面）"""
        return True

    def on_resume(self):
        """处理应用恢复"""
        pass

if __name__ == "__main__":
    BillApp().run()

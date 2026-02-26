# Skill: COROS 训练计划自动填充

## 概述
使用 chrome-devtools MCP 工具自动将训练计划数据填充到 COROS Training Hub (t.coros.com/schedule-plan/add)。

## 前置条件

### 1. 安装 chrome-devtools MCP
```bash
code --add-mcp '{"name":"chrome-devtools","command":"npx","args":["-y","chrome-devtools-mcp@latest"]}'
```

### 2. 配置 .vscode/mcp.json
```json
{
  "servers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"]
    }
  }
}
```

### 3. 启动 Chrome 调试模式
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 "https://t.coros.com/schedule-plan/add" &
```

## 核心操作流程

### 1. 导航到页面
```javascript
mcp_chrome-devtoo_navigate_page({ url: "https://t.coros.com/schedule-plan/add" })
```

### 2. 填写计划描述
```javascript
mcp_chrome-devtoo_fill({ uid: "描述框uid", value: "训练计划描述" })
```

### 3. 添加单日训练的函数
```javascript
// 定义添加训练卡片的函数
window.addTraining = function(weekIndex, dayIndex) {
  // 每周有8列：周一-周日 + 周统计
  // dayIndex: 1=周一, 2=周二, ..., 7=周日
  const weekDays = document.querySelectorAll('.calender-week-day');
  const cellIndex = (weekIndex - 1) * 8 + (dayIndex - 1);
  const cell = weekDays[cellIndex];
  
  if (cell) {
    const addCard = cell.querySelector('.add-card');
    if (addCard) {
      addCard.classList.remove('hidden');
      addCard.style.display = 'flex';
      addCard.click();
      return "Success";
    }
  }
  return "Failed";
};
```

### 4. 点击"训练"选项
```javascript
// 查找并点击"训练"菜单项
const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
let node;
while (node = walker.nextNode()) {
  if (node.textContent === '训练') {
    const parent = node.parentElement;
    if (parent && parent.offsetParent !== null) {
      parent.click();
      break;
    }
  }
}
```

### 5. 填写训练表单
```javascript
// 填写训练名称
const nameInput = document.querySelector('input[value="训练"]');
if (nameInput) {
  nameInput.value = '轻松跑 40min';
  nameInput.dispatchEvent(new Event('input', { bubbles: true }));
}

// 填写描述
const descTextarea = document.querySelector('.arco-modal textarea');
if (descTextarea) {
  descTextarea.value = "5'15\"-5'30\" Zone 2";
  descTextarea.dispatchEvent(new Event('input', { bubbles: true }));
}

// 设置时间
const timeInput = document.querySelector('.arco-picker-start-time');
if (timeInput) {
  timeInput.value = '00:40:00';
  timeInput.dispatchEvent(new Event('input', { bubbles: true }));
  timeInput.dispatchEvent(new Event('change', { bubbles: true }));
}

// 保存
const buttons = document.querySelectorAll('.arco-modal button');
for (const btn of buttons) {
  if (btn.innerText.includes('保存')) {
    btn.click();
    break;
  }
}
```

### 6. 保存整个计划
```javascript
mcp_chrome-devtoo_click({ uid: "保存按钮uid" })
```

## 训练数据格式
```javascript
const trainingPlan = [
  {week: 1, day: 4, name: "轻松跑 40min", time: "00:40:00", note: "Zone 2"},
  {week: 1, day: 6, name: "越野模拟 15km", time: "02:30:00", note: "含800m爬升"},
  {week: 1, day: 7, name: "耐力跑 60min", time: "01:00:00", note: "巡航跑"},
  // ... 更多训练
];
```

## COROS 页面结构
- **训练类型**: 跑步（默认）
- **训练名称**: 自定义名称
- **目标类型**: 时间 (h:m:s)
- **强度类型**: %乳酸阈心率 / 有氧动力区
- **描述**: 训练备注

## 注意事项
1. 每添加一个训练后需等待对话框关闭再添加下一个
2. 周索引从1开始，日索引1-7对应周一到周日
3. 页面使用 Arco Design 组件库
4. 时间格式为 `HH:MM:SS`
5. 添加训练前需要 hover 显示 +号按钮

## 常用 MCP 工具
- `mcp_chrome-devtoo_navigate_page` - 导航到页面
- `mcp_chrome-devtoo_take_snapshot` - 获取页面DOM结构
- `mcp_chrome-devtoo_take_screenshot` - 截图
- `mcp_chrome-devtoo_click` - 点击元素
- `mcp_chrome-devtoo_fill` - 填写输入框
- `mcp_chrome-devtoo_evaluate_script` - 执行JavaScript
- `mcp_chrome-devtoo_hover` - 悬停元素

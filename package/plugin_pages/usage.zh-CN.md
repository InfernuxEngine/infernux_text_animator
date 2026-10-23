# 文字动画

开启「解析效果标签」后，可以使用 `<wave amplitude=2>文字</wave>`、嵌套效果和
Inspector 中的命名预设。`<event=名称/>` 触发标记事件，`<wait=0.5/>` 控制打字停顿。
原生颜色/字号标签仍由 `UIText.rich_text` 单独控制。

出入场可组合淡入淡出、缩放、偏移、旋转、顶点扩张和确定随机方向，按打字机的实际
时间启动；消失动画完成前保持字形可见。字符事件可驱动现有 AudioSource 发声。
`CharacterAnimator` 支持字符、区间、单词和行的手动修改，多次修改后统一 `Apply()`。

通过 `TextAnimation(text, effects)` 为现有 `UIText` 添加持续字效。调用
`Update(delta_time)` 或 `Sample(time)` 求值，`Reset()` 仅清除自己的效果层。
`Effect` 可指定字符区间、振幅、速度、逐字相位差和起始相位。速度单位为每秒
周期数，相位单位为弧度；可据此准确复现指定的正弦波动公式。

`Typewriter(text).ShowText(value)` 按原生字素逐字显示；可通过
`StopShowingText` 暂停、`StartShowingText` 继续、`SkipTypewriter` 跳过，
通过 `StartDisappearingText` 隐藏已显示的字。可设置开始、逐字、完成和隐藏
回调，跳过时是否触发逐字事件由调用者明确选择。

暂停后也可以直接跳过，完成事件只发送一次，重复调用 `SkipTypewriter` 不会重发。
传入 `trigger_events=True` 会额外执行剩余的显示字符和标记回调。组件的 `Pause()`、
`Play()` 同时控制持续字效、打字机与出入场；低层 `Typewriter` 则由调用方显式执行
`Update(delta_time)`。

字符事件使用原生排版后的字素：富文本 `<br>` 返回换行，空白字符不播放打字音效。
修改出入场设置会保留当前显示/隐藏进度与暂停状态。`SetEffects([])` 清除 Effects 层，
不影响 Manual 和 Appearance 层。

标记按文字中的顺序执行；词内标记会在该处切分显示，普通整词仍一起出现。
回调中的暂停立即停在该处，本帧剩余时间不再推进持续字效或出入场；继续时不重放
标记。暂停后可以跳过，跳过期间再次暂停则停在那里。`ShowText` 可替换尚未完成的
退场；只改标签时复用原生布局并更新效果与事件，移除字效时立即清理效果层。

手动字符几何可批量修改后一次提交：

```python
from infernux_text_animator import CharacterAnimator

characters = CharacterAnimator(label)
characters.Word(0).Offset((0, -8)).Rotate(-5)
characters.Range().Alpha(0.8)
characters.Apply()
```

Manual、Effects、Appearance 三层依次组合。同一文字使用一个 Manual 层控制器；
改变布局后应刷新选择，不再需要手动变形时调用 `Reset()` 还原。

可在 UIText 上添加“Animation / Text Animator”组件，通过引擎通用列表控件
编辑效果与打字机参数。组件共用一个更新入口，暂停、空效果或打字结束后
关闭无用更新；禁用时恢复自己的几何层与可见数。编辑模式打开“动画 / 文字动画”，
选中对象后可以预览、暂停和停止还原。保存、撤销、切换选择或进入 Play 都会先结束
预览、恢复原始文字。预览不发送游戏事件，也不播放打字音效。

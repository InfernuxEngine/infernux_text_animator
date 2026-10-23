# 文字动画

开启「解析效果标签」后，可以使用 `<wave amplitude=2>文字</wave>`、嵌套效果和
Inspector 中的命名预设。`<event=名称/>` 触发标记事件，`<wait=0.5/>` 控制打字停顿。
原生颜色/字号标签仍由 `UIText.rich_text` 单独控制。

入场和退场分别配置，可组合淡入淡出、缩放、偏移、旋转、顶点扩张和确定随机方向，按打字机的实际
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

`TextAnimator.SetTypewriterSpeed(2)` 将当前打字速度加倍，不会重新开始或重放事件。
「打字速度倍率」独立于「每秒字符数」保存，禁用后重新启用仍然保留。倍率必须为有限正数，
停止请使用 Pause。每次推进固定使用调用开始时的倍率，回调中的修改从下一次推进生效。
字符间隔与 wait 标签一起缩放，持续字效和字素出入场时长保持各自的计时。
低层 writer 可直接设置 `timeScale`；`elapsed_time` 是逻辑打字时间，`playback_time` 是
结合已使用倍率得到的呈现时间，用于字素外观。Skip 可以直接跳过这段时间，无需实际等待。

入场与退场分别设置时长、变形和随机种子。`PlayAppearance()` 与 `PlayAppearance(False)`
会取代当前打字，分别使用「整段入场逐字间隔」和「整段退场逐字间隔」播放整段外观；
打字模式下，字素启动间隔仍由打字速度控制。未完成时反向，会在同一个 Appearance 层中
从当前偏移、旋转、缩放、透明度和顶点状态继续，不因两套配置不同而跳变。同一原生布局
重新显示时保留当前可绘制的字素；不同布局重新绑定，不将无关文字做字形变形过渡。
等待新显示逐字接管期间，字素保持当前几何，已被取代的旧退场不再继续推进。
运行中修改配置会保留当前外观并调整剩余时长。两个阶段均使用 cubic-out 缓动。
独立外观播放也支持 Pause/Play；SkipTypewriter 仅跳过打字流程。

```python
animator.appearance.duration = 0.3
animator.appearance.offset = (0, 12)
animator.disappearance.duration = 0.1
animator.disappearance.offset = (-8, 0)
animator.SetTypewriterSpeed(2)
animator.ShowText("你好，世界")
# 之后隐藏：animator.StartDisappearingText()
```

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

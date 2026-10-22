# 文字动画

通过 `TextAnimation(text, effects)` 为现有 `UIText` 添加持续字效。调用
`Update(delta_time)` 或 `Sample(time)` 求值，`Reset()` 仅清除自己的效果层。
`Effect` 可指定字符区间、振幅、速度、逐字相位差和起始相位。速度单位为每秒
周期数，相位单位为弧度；可据此准确复现指定的正弦波动公式。

`Typewriter(text).ShowText(value)` 按原生字素逐字显示；可通过
`StopShowingText` 暂停、`StartShowingText` 继续、`SkipTypewriter` 跳过，
通过 `StartDisappearingText` 隐藏已显示的字。可设置开始、逐字、完成和隐藏
回调，跳过时是否触发逐字事件由调用者明确选择。

可在 UIText 上添加“Animation / Text Animator”组件，通过引擎通用列表控件
编辑效果与打字机参数。组件共用一个更新入口，暂停、空效果或打字结束后
关闭无用更新；禁用时恢复自己的几何层与可见数。标记与出入场预设仍在开发中。

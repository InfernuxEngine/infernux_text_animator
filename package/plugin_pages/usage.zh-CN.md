# 文字动画

通过 `TextAnimation(text, effects)` 为现有 `UIText` 添加持续字效。调用
`Update(delta_time)` 或 `Sample(time)` 求值，`Reset()` 仅清除自己的效果层。
`Effect` 可指定字符区间、振幅、速度和相位。

`Typewriter(text).ShowText(value)` 按原生字素逐字显示；可通过
`StopShowingText` 暂停、`StartShowingText` 继续、`SkipTypewriter` 跳过，
通过 `StartDisappearingText` 隐藏已显示的字。可设置开始、逐字、完成和隐藏
回调，跳过时是否触发逐字事件由调用者明确选择。

当前为开发阶段的代码接口，可视化组件、标记和出入场预设仍在开发中。

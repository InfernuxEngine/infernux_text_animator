# 文字动画

需要 Infernux 0.4.3 hotfix 4 或以后版本。Preload 只检查一次原生字符颜色能力，
缺失时明确提示需要更新引擎。

开启「解析效果标签」后，可以使用 `<wave a=2 s=0.6>文字</wave>`、嵌套效果和
Inspector 中的命名预设。`<?名称>` 触发标记事件，`<waitfor=0.5>` 控制打字停顿。
原生颜色/字号标签仍由 `UIText.rich_text` 单独控制。
效果标签不关闭时延伸到末尾，`</>` 关闭全部持续字效。`<noparse>...</noparse>`
保留内部标签字面内容；原生颜色/字号/br 的保护需要原生 noparse 热修及 rich-text 模式。
`{fade}`、`{incr}`、`{slideh}`、`{rot}` 分别指定入场淡入、缩放、横移、旋转；
加 `#` 的 `{#fade}`、`{#incr}`、`{#slideh}`、`{#rot}` 指定退场。
`{/}` / `{/#}` 分别关闭该类别的标签。这些范围无需开启组件的默认外观，支持叠加，
并在同一个 Appearance buffer 内保留各通道时钟，例如 `{fade s=2}{incr}你好{/}`
会让淡入速度是缩放的两倍。`a` 控制强度，`s` 控制正数速度倍率；基准时长沿用 Inspector
的入场、退场配置。原生默认强度为完整淡入/淡出、零到完整缩放、8 本地单位横移、90 度旋转。
这些原生端点效果与所有已有 Effect/命名 CustomEffect 均可用于三类标签，例如
`<fade>`、`{wave}`、`{#wave}`。动态出入场按每个字素的局部时钟求值，再通过有限包络
回到静止状态，仍只提交现有 Appearance 层；共享同一时钟的字素批量调用自定义效果。
这不代表包含了上游所有样本资源与 playback 数据库。
数值 modifier 支持 `a=5` 直接设置和 `a*3` 乘基础值；重复字段只采用最后一项。
`<wave once>` 播放一个原生周期后清除自身几何，无其他播放任务时退出调度；
新的 Show 可以再次播放一次性效果。

入场和退场分别配置，可组合淡入淡出、缩放、偏移、旋转、顶点扩张和确定随机方向，按打字机的实际
时间启动；消失动画完成前保持字形可见。字符事件可驱动现有 AudioSource 发声。
`CharacterAnimator` 支持字符、区间、单词和行的手动修改，多次修改后统一 `apply()`。
手动颜色/透明度使用绝对值，元素与父节点的 opacity 仍独立控制整体透明度。

通过 `TextAnimation(text, effects)` 为现有 `UIText` 添加持续字效。调用
`update(delta_time)` 或 `sample(time)` 求值，`reset()` 仅清除自己的效果层。
`Effect` 可指定字符区间、振幅、速度、逐字相位差和起始相位。速度单位为每秒
周期数，相位单位为弧度；可据此准确复现指定的正弦波动公式。

`Typewriter(text).show_text(value)` 按原生字素逐字显示；可通过
`stop_showing_text` 暂停、`start_showing_text` 继续、`skip_typewriter` 跳过，
通过 `start_disappearing_text` 隐藏已显示的字。可设置开始、逐字、完成和隐藏
回调，跳过时是否触发逐字事件由调用者明确选择。

暂停后也可以直接跳过，完成事件只发送一次，重复调用 `skip_typewriter` 不会重发。
跳过前设置 `trigger_events_on_skip = True`，会额外执行剩余的显示字符和标记回调。组件的 `pause_animation()`、
`resume_animation()` 同时控制持续字效、打字机与出入场；低层 `Typewriter` 则由调用方显式执行
`update(delta_time)`。

字符事件使用原生排版后的字素：富文本 `<br>` 返回换行，空白字符不播放打字音效。
修改出入场设置会保留当前显示/隐藏进度与暂停状态。`set_effects([])` 清除 Effects 层，
不影响 Manual 和 Appearance 层。

标记按文字中的顺序执行；词内标记会在该处切分显示，普通整词仍一起出现。
回调中的暂停立即停在该处，本帧剩余时间不再推进持续字效或出入场；继续时不重放
标记。暂停后可以跳过，跳过期间再次暂停则停在那里。`show_text` 可替换尚未完成的
退场；只改标签时复用原生布局并更新效果与事件，移除字效时立即清理效果层。

`TextAnimator.set_typewriter_speed(2)` 将当前打字速度加倍，不会重新开始或重放事件。
「打字速度倍率」独立于「每秒字符数」保存，禁用后重新启用仍然保留。倍率必须有限且不小于 0.001，
停止请使用 pause_animation。每次推进固定使用调用开始时的倍率，回调中的修改从下一次推进生效。
字符间隔与 waitfor 标签一起缩放，持续字效和字素出入场时长保持各自的计时。
低层 writer 可直接设置 `speed_multiplier`；`elapsed_time` 是逻辑打字时间，`playback_time` 是
结合已使用倍率得到的呈现时间，用于字素外观。Skip 可以直接跳过这段时间，无需实际等待。

入场与退场分别设置时长、变形和随机种子。`play_appearance()` 与 `play_appearance(False)`
会取代当前打字，分别使用「整段入场逐字间隔」和「整段退场逐字间隔」播放整段外观；
打字模式下，字素启动间隔仍由打字速度控制。未完成时反向，会在同一个 Appearance 层中
从当前偏移、旋转、缩放、透明度和顶点状态继续，不因两套配置不同而跳变。同一原生布局
重新显示时保留当前可绘制的字素；不同布局重新绑定，不将无关文字做字形变形过渡。
等待新显示逐字接管期间，字素保持当前几何，已被取代的旧退场不再继续推进。
运行中修改配置会保留当前外观并调整剩余时长。两个阶段均使用 cubic-out 缓动。
独立外观播放也支持 pause_animation/resume_animation；skip_typewriter 仅跳过打字流程。

```python
animator.appearance.duration = 0.3
animator.appearance.offset = (0, 12)
animator.disappearance.duration = 0.1
animator.disappearance.offset = (-8, 0)
animator.set_typewriter_speed(2)
animator.show_text("你好，世界")
# 之后隐藏：animator.start_disappearing_text()
```

手动字符几何可批量修改后一次提交：

```python
from infernux_text_animator import CharacterAnimator

characters = CharacterAnimator(label)
characters.word(0).offset((0, -8)).rotate(-5)
characters.range().alpha(0.8)
characters.apply()
```

Manual、Effects、Appearance 三层依次组合。同一文字使用一个 Manual 层控制器；
改变布局后应刷新选择，不再需要手动变形时调用 `reset()` 还原。

可在 UIText 上添加“Animation / Text Animator”组件，通过引擎通用列表控件
编辑效果与打字机参数。组件在每个自动更新阶段共用一个入口，暂停、空效果或打字结束后
关闭无用更新；禁用时恢复自己的几何层与可见数。编辑模式打开“动画 / 文字动画”，
选中对象后可以预览、暂停和停止还原。保存、撤销、切换选择或进入 play 都会先结束
预览、恢复原始文字。预览不发送游戏事件，也不播放打字音效。

公开函数统一使用 `snake_case`，不保留旧别名；类名仍使用 PascalCase。
控制函数返回 `None`：`show_text(text: str)` 必须传入字符串，继续当前内容使用
`start_showing_text(restart=False)`，传入 `True` 则从头开始。
`stop_showing_text()` 与 `stop_disappearing_text()` 分别停止显示和隐藏；
`skip_typewriter()` 无参数，是否派发剩余回调由「跳过时触发事件」配置控制。
`trigger_visible_events()` / `trigger_remaining_events()` 只发送尚未触发的标记，
不改变可见字符数或时钟；`skip_current_action()` 返回是否跳过了当前的计时等待、
输入等待或自定义动作；跳过自定义动作时会取消该动作。
`get_approximate_show_duration()` / `get_approximate_hide_duration()` 查询近似时长，
不计标签、用户回调或字素外观动画耗时。
停止显示/隐藏只停止相应打字方向，持续字效和已经开始的字素过渡继续运行；
要冻结整个组件请使用 `pause_animation()`。

`on_character_visible` 接收一个 `CharacterData`，包含 `index`、`info.character`
（原生显示字素）与 `info.native`（原生布局元数据）。`on_message` 接收一个
`EventMarker`，包含 `name: str` 与 `parameters: list[str]`；例如
`<?奖励=10,金币>` 的 `"10"` 始终是字符串，不自动变成数值或枚举。
`on_typewriter_start`、`on_text_showed`、`on_text_disappeared` 不带参数。
`on_character_wait_started` / `on_character_wait_finished` 接收
`(CharacterData, WaitMode)`，回调可以在该等待边界暂停或替换播放。
当前原生适配器的 `WaitMode.APPEARANCE` / `DISAPPEARANCE` 表示显示、隐藏方向。
官方 Unity API 页面未列出 core 枚举成员；仍需从获授权的正式 core 包核实其成员、
数值和语义。这一项尚未完成对齐，不能将当前定义视作已确认的上游契约。

组件 `set_text(text: str, hide_text: bool = False)` 立即替换文字并取消旧打字流程；
`swap_text(text: str)` 保留原有可见前缀或逐字可见状态，再按新布局的字素索引应用。
`append_text(appended_text: str, hide_text: bool = False, skip_old_text: bool = True)`
追加文字，不重复派发旧标记。`skip_old_text=False` 时保留旧等待、外观进度和标记顺序；
`hide_text=False` 时追加部分立即可见。

`set_visibility_char(index: int, is_visible: bool, can_play_effects: bool = True)`、
`set_visibility_word(index: int, is_visible: bool, can_play_effects: bool = True)` 与
`set_visibility_entire_text(is_visible: bool, can_play_effects: bool = True)` 分别控制
原生字素、单词或整段可见性。`can_play_effects=False` 时立即应用。逐字覆盖会在后续
打字期间保持生效，复用现有 Appearance 层。
`set_appearances_active(is_category_enabled: bool)` 禁用时保留语义可见状态、结束外观过渡；
`set_behaviors_active(is_category_enabled: bool)` 只清理或恢复持续字效层，两者均保留配置。
这些组件控制函数均返回 `None`。`pause_animation()` / `resume_animation()` 统一控制
各动画阶段，状态可由 `is_animation_paused` 查询，不保留 play/pause 旧别名。
签名基线为 Text Animator for Unity 3.22.1 的公开 base component/typewriter API；
原生字效与外观辅助接口复用 Infernux 的文本几何和层组合。

API 配置必须传入枚举：`EffectKind.WAVE`、`CurveTarget.OFFSET_Y`、
`TimeScale.SCALED` / `UNSCALED`。成员使用大写命名，存储值保持稳定；
构造参数不接受裸字符串代替枚举。标签名称在文本解析边界仍然是字符串。
组件 `time_scale` 选择游戏时间或实际时间，数值倍率使用独立的 `speed_multiplier`。
`TextAnimation.set_text(text: str, hide_text: bool = False)` 立即显示或隐藏新文本；
这里的布尔参数不代表 TMP 的输入框同步选项。批量字符选择与外观配置属于原生扩展。
内置端点配置采用文本平面坐标；自定义字效还可编辑原生仿射变换和顶点深度，
不另建一套 TMP 组件层次。

`<speed=2>` 将当前段落后续打字速度乘以 2，长帧跨过标签时也会按剩余真实时间
计算后续进度；它不修改保存的打字倍率，也不加快持续字效或外观动画。
`<waitinput>` 等待后续原生输入帧中的新按键、鼠标或触摸，期间持续字效和已启动的
字素过渡继续播放。Skip 与 `skip_current_action()` 均可越过输入等待。
`input_mode` 使用 `WaitInputMode.ANY_INPUT`（默认）或 `SPECIFIC_ACTION`。
指定动作时，把原生 `InputAction` 按字符串标识放入 `input_actions`；
`<waitinput=confirm>` 查询该动作的 `was_pressed_this_frame`。不传参数时使用
`default_input_key`，`any` 参数始终表示任意输入。未知动作标识属于配置错误，
不会自动退回到某个物理键。

`animation_loop` 使用 `AnimationLoop.UPDATE`、`LATE_UPDATE`、`SCRIPT`
（值为 0、1、2）。自动模式在相应引擎阶段运行；Script 关闭自动更新，改由
`animate(delta_time: float) -> None` 手动推进正在播放的组件。`pause_animation()`
也会冻结手动推进。

`characters`、`characters_count`、`words`、`words_count` 访问当前原生布局。
`CharacterData.is_visible` 表示语义可见性，结合逐字标记以及独立的
`first_visible_character` / `max_visible_characters` 边界（`-1` 为无上限）；
改变边界不会覆盖逐字标记。`all_letters_shown`、`any_letter_visible`、
`latest_character_shown` 和显示/隐藏/等待状态可用于查询流程，尚未显示过字符或空文本
的 latest 为 `None`。`text_full` 保留源标签，`text_without_text_anim_tags`
保留原生富文本，`text_without_any_tag` 返回原生实际显示内容；未开启原生富文本解析时，
原生标签仍是字面内容。替换文本会重绑当前数据及事件，显式派发标记不再执行旧文本的 cue。

`all_letters_shown` 还会等待入场完成；退场中仍有可见透明度的字素会使
`any_letter_visible` 保持为 True。`trigger_visible_events()` 同时过滤首字符、最大可见数
以及逐字可见标记，`trigger_remaining_events()` 则不受可见性限制。

`appearances`、`behaviors`、`disappearances` 返回 `TextRegion(start, end, effect)`，
包含实际生效的默认效果区间，end 为不包含的结束索引。`default_tags_mode` 传入
`DefaultEffectsMode.FALLBACK`（只作用没有该类显式标签的字素）或 `CONSTANT`（始终叠加）。
这两个枚举使用本插件的语义字符串值，不假定未公开的上游数值。
`use_dynamic_scaling=True` 时，像素偏移与顶点按 `UIText.font_size/reference_font_size`
缩放，原生参考字号为 18；颜色、旋转和缩放倍率不随字号改变。

`try_initializing_once()` 只初始化一次，不重播已绑定的内容；`force_database_refresh()`
重新解析命名效果/样式；`refresh_all_effect_states()` 更新设置并保留效果进度与暂停状态。
若变化导致 cue 顺序或布局改变，则建立新的打字绑定。`schedule_mesh_refresh()` 在下次循环
刷新一次几何，暂停时也可执行，且不推进时钟。这四个无参函数均返回 None。

`database_effects` 保存命名自定义字效，`database` 保存命名动作工厂。
动作工厂实现 `create_action_from(marker: ActionMarker, typewriter: object) -> ActionState`；
每次遇到标签创建一个状态，状态实现 `progress(delta_time: float, typing_info: TypingInfo)
-> ActionStatus` 与 `cancel() -> None`。返回 `RUNNING` 阻塞或 `FINISHED` 继续，必须使用
枚举而非裸字符串。参数保持字符串列表，暂停保留状态，跳过、换文字和禁用会取消状态。
自定义动作消耗本次 progress 收到的时间，后续字素从该次更新边界开始；原生 TypingInfo
提供控制器、已过呈现时间和可修改的打字速度。

`timing_settings` 可替换为 `TypingDelaysByCharacter()` / `TypingDelaysByWord()`，
或继承 `TypingTimings` 实现 `get_wait_appearance_time_of(character, animator) -> float`；
退场等待默认复用它，也可以重写 `get_wait_disappearance_time_of`。输入是绑定好的
CharacterData，返回非负有限等待时间。运行中更换规则，会在当前字符等待边界重建后续
显示组，不重放已执行 cue。`style_sheet["accent"] = TextStyle("<wave>", "</wave><?done>")`
可复用一组效果与事件，样式标签大小写不敏感，并保留 noparse 保护。

这些 Python 对象承接公开的自定义动作、计时和样式能力，不创建另一套 ScriptableObject。
官方 core 的 `StartTypewriterMode` flags 与 `WaitMode` 成员仍缺少可核实来源；当前原生
自动播放与显式 Show/Start 可正常工作，但不宣称存在同类型的官方 flags 契约。

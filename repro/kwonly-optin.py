"""边界面板：hookimpl 声明 keyword-only 参数（def hook(self, *, a)）时，
按名字 opt-in 取参是否可用；以及三条既有语义是否保持不变。

用法（在仓库根目录）：
    timeout 120 env PYTHONPATH=src .venv/bin/python <此文件>
"""

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager
from pluggy import PluginValidationError
from pluggy._hooks import varnames


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")

CALLS: list[str] = []


def make_pm(spec_kwonly: bool = False) -> PluginManager:
    pm = PluginManager("example")

    class Hooks:
        if spec_kwonly:

            @hookspec
            def hello(self, *, a, b):
                raise NotImplementedError()

        else:

            @hookspec
            def hello(self, a, b):
                raise NotImplementedError()

    pm.add_hookspecs(Hooks)
    return pm


CHECKS: list[tuple[str, object]] = []


def check(label):
    def deco(fn):
        CHECKS.append((label, fn))
        return fn

    return deco


@check("L1 impl 只有 kw-only 参数：按名字收到调用方的值")
def _l1():
    pm = make_pm()

    class P:
        @hookimpl
        def hello(self, *, a):
            CALLS.append(f"a={a}")

    pm.register(P())
    pm.hook.hello(a=1, b=2)
    return CALLS == ["a=1"]


@check("L2 impl 混合位置 + kw-only：两种传参都按名字给值")
def _l2():
    pm = make_pm()

    class P:
        @hookimpl
        def hello(self, a, *, b):
            CALLS.append(f"{a}/{b}")

    pm.register(P())
    pm.hook.hello(a=1, b=2)
    return CALLS == ["1/2"]


@check("L3 impl 的 kw-only 名字不在 spec 里：注册时就 PluginValidationError")
def _l3():
    pm = make_pm()

    class P:
        @hookimpl
        def hello(self, *, nope):
            raise NotImplementedError()  # pragma: no cover

    try:
        pm.register(P())
    except PluginValidationError:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


@check("L4 spec 自己声明 kw-only 参数：位置形式的 impl 能 opt-in 它")
def _l4():
    pm = make_pm(spec_kwonly=True)

    class P:
        @hookimpl
        def hello(self, a):
            CALLS.append(f"a={a}")

    pm.register(P())
    pm.hook.hello(a=1, b=2)
    return CALLS == ["a=1"]


@check("L5 带默认值的 kw-only：与带默认值的位置参数一致，调用方的值不传入")
def _l5():
    pm = make_pm()

    class P:
        @hookimpl
        def hello(self, *, a=7):
            CALLS.append(f"a={a}")

    pm.register(P())
    pm.hook.hello(a=1, b=2)
    return CALLS == ["a=7"]


@check("L6 位置专用（/ 之后）参数的 impl 仍按位置收到值")
def _l6():
    pm = make_pm()

    class P:
        @hookimpl
        def hello(self, a, /):
            CALLS.append(f"pos-a={a}")

    pm.register(P())
    pm.hook.hello(a=1, b=2)
    return CALLS == ["pos-a=1"]


@check("L7 可调用对象插件的 __call__ 也支持 kw-only opt-in")
def _l7():
    pm = make_pm()

    class P:
        def __call__(self, *, b):
            CALLS.append(f"call-b={b}")

    hookimpl(P.__call__)
    impl = P()
    setattr(impl, "hello", impl.__call__)
    pm.register(impl, name="callable-plugin")
    pm.hook.hello(a=1, b=2)
    return CALLS == ["call-b=2"]


@check("L8 新行为不改变 varnames 的返回值形状（既有公开助手）")
def _l8():
    def f1(x, *, y):
        raise NotImplementedError()  # pragma: no cover

    def f2(x, *, y=3):
        raise NotImplementedError()  # pragma: no cover

    return varnames(f1) == (("x",), ()) and varnames(f2) == (("x",), ())


@check("L9 现成场景回归：互斥位置参数的两个 impl（opt-in args）")
def _l9():
    pm = PluginManager("example")

    class Hooks:
        @hookspec
        def hello(self, arg1, arg2, common_arg):
            raise NotImplementedError()

    class P1:
        @hookimpl
        def hello(self, arg1, common_arg):
            return arg1 + common_arg

    class P2:
        @hookimpl
        def hello(self, arg2, common_arg):
            return arg2 + common_arg

    pm.add_hookspecs(Hooks)
    pm.register(P1())
    pm.register(P2())
    return pm.hook.hello(arg1=1, arg2=2, common_arg=0) == [2, 1]


@check("L10 wrapper / 旧式 hookwrapper 形式的 impl 也能 kw-only opt-in")
def _l10():
    pm = make_pm()

    class W:
        @hookimpl(wrapper=True)
        def hello(self, *, a):
            res = yield
            CALLS.append(f"w-a={a}")
            return res

    class HW:
        @hookimpl(hookwrapper=True)
        def hello(self, *, b):
            CALLS.append(f"hw-b={b}")
            yield

    class Q:
        @hookimpl
        def hello(self, a):
            return [f"inner:{a}"]

    pm.register(W())
    pm.register(HW())
    pm.register(Q())
    pm.hook.hello(a=1, b=2)
    return sorted(CALLS) == ["hw-b=2", "w-a=1"]


print(f"panel: {len(CHECKS)} checks")
passed = 0
for label, fn in CHECKS:
    CALLS.clear()
    try:
        ok = bool(fn())
        detail = ""
    except Exception as exc:  # noqa: BLE001
        ok = False
        detail = f" (raised {type(exc).__name__}: {exc})"
    passed += ok
    print(("PASS " if ok else "FAIL ") + label + ("" if ok else detail))
print(f"SUMMARY {passed}/{len(CHECKS)}")

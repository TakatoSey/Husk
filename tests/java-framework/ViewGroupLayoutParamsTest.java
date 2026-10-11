import android.content.Context;
import android.content.ContextWrapper;
import android.view.View;
import android.view.ViewGroup;

/** Runs against Husk's actual framework classes on a host JVM, without native graphics. */
public final class ViewGroupLayoutParamsTest {
    static final Context CONTEXT = new ContextWrapper(null);

    static final class Parent extends ViewGroup {
        Parent() { super(CONTEXT); }
        @Override protected void onLayout(boolean changed, int l, int t, int r, int b) {}
        boolean addDuringLayout(View child, LayoutParams params, boolean suppress) {
            return addViewInLayout(child, -1, params, suppress);
        }
        @Override protected boolean checkLayoutParams(LayoutParams params) {
            return params instanceof MarginLayoutParams;
        }
        @Override protected LayoutParams generateLayoutParams(LayoutParams params) {
            return new MarginLayoutParams(params);
        }
    }

    // EpoxyRecyclerView initializes its layout manager on the first setLayoutParams call.
    static final class EpoxyLikeView extends View {
        int calls;
        boolean managerReady;
        EpoxyLikeView() { super(CONTEXT); }
        @Override public void setLayoutParams(ViewGroup.LayoutParams params) {
            boolean first = getLayoutParams() == null;
            if (getParent() != null) throw new AssertionError("callback must precede parent assignment");
            calls++;
            super.setLayoutParams(params);
            if (first) managerReady = true;
        }
    }

    static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        Parent parent = new Parent();
        EpoxyLikeView child = new EpoxyLikeView();
        parent.addView(child, new ViewGroup.LayoutParams(120, 240));
        check(child.calls == 1 && child.managerReady, "addView must initialize the child's layout manager");
        check(child.getLayoutParams() instanceof ViewGroup.MarginLayoutParams, "callback must receive converted params");
        check(child.getLayoutParams().width == 120 && child.getParent() == parent, "params and parent must be preserved");

        EpoxyLikeView during = new EpoxyLikeView();
        new Parent().addDuringLayout(during, new ViewGroup.LayoutParams(10, 20), false);
        check(during.calls == 1 && during.managerReady, "unsuppressed addViewInLayout must dispatch the setter");

        EpoxyLikeView suppressed = new EpoxyLikeView();
        Parent suppressedParent = new Parent();
        suppressedParent.addDuringLayout(suppressed, new ViewGroup.LayoutParams(30, 40), true);
        check(suppressed.calls == 0 && !suppressed.managerReady, "suppressed path must bypass the setter");
        check(suppressed.getLayoutParams().height == 40 && suppressed.getParent() == suppressedParent,
              "suppressed path must still assign params and parent");
        System.out.println("PASS: ViewGroup dispatches layout params and preserves the suppressed path");
    }
}

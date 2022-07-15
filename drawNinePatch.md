## 关于延迟绘图
### 绘制过程
在`SkiaOpenGLPipeline::draw()`时:
```
// frameworks/base/libs/hwui/pipeline/skia/SkiaOpenGLPipeline.cpp
bool SkiaOpenGLPipeline::draw(const Frame& frame, const SkRect& screenDirty, const SkRect& dirty,
                              const LightGeometry& lightGeometry,
                              LayerUpdateQueue* layerUpdateQueue, const Rect& contentDrawBounds,
                              bool opaque, const LightInfo& lightInfo,
                              const std::vector<sp<RenderNode>>& renderNodes,
                              FrameInfoVisualizer* profiler) {
    ... ...
    renderFrame(*layerUpdateQueue, dirty, renderNodes, opaque, contentDrawBounds, surface,
                SkMatrix::I());
    ... ...
}

// frameworks/base/libs/hwui/pipeline/skia/SkiaPipeline.cpp
void SkiaPipeline::renderFrame(const LayerUpdateQueue& layers, const SkRect& clip,
                               const std::vector<sp<RenderNode>>& nodes, bool opaque,
                               const Rect& contentDrawBounds, sk_sp<SkSurface> surface,
                               const SkMatrix& preTransform) {
    ... ...
    SkCanvas* canvas = tryCapture(surface.get(), nodes[0].get(), layers);
    // draw all layers up front
    renderLayersImpl(layers, opaque);
    renderFrameImpl(clip, nodes, opaque, contentDrawBounds, canvas, preTransform);
    ... ...
}
void SkiaPipeline::renderFrameImpl(const SkRect& clip,
                                   const std::vector<sp<RenderNode>>& nodes, bool opaque,
                                   const Rect& contentDrawBounds, SkCanvas* canvas,
                                   const SkMatrix& preTransform) {
    ... ...
    if (1 == nodes.size()) {
        if (!nodes[0]->nothingToDraw()) {
            RenderNodeDrawable root(nodes[0].get(), canvas);
            root.draw(canvas);
        }
    } else ... ...
    ... ...
}
```
`RenderNodeDrawable`的基类是`SkDrawable`, 因此:
```
// external/skia/src/core/SkDrawable.cpp
void SkDrawable::draw(SkCanvas* canvas, const SkMatrix* matrix) {
    ... ...
    this->onDraw(canvas);
    ... ...
}
```
调回子类`RenderNodeDrawable::onDraw()`:
```
// frameworks/base/libs/hwui/pipeline/skia/RenderNodeDrawable.cpp
void RenderNodeDrawable::onDraw(SkCanvas* canvas) {
    ... ...
    if ((!mInReorderingSection) || MathUtils::isZero(mRenderNode->properties().getZ())) {
        this->forceDraw(canvas);
    }
}

void RenderNodeDrawable::forceDraw(SkCanvas* canvas) const {
    RenderNode* renderNode = mRenderNode.get();
    ... ...
    if (!properties.getProjectBackwards()) {
        drawContent(canvas);
        ... ...
    }
    displayList->mProjectedOutline = nullptr;
}

void RenderNodeDrawable::drawContent(SkCanvas* canvas) const {
```
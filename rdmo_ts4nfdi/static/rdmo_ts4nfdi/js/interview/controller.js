export class InterviewAnnotationController {
    constructor({host, api, inlineRenderer, drawer}) {
        this.host = host;
        this.api = api;
        this.inlineRenderer = inlineRenderer;
        this.drawer = drawer;
        this.pageKey = null;
        this.revision = 0;
        this.listRequest = null;
        this.detailRequest = null;
        this.stopObserving = null;
        this.stopDrawer = null;
    }

    start() {
        this.stopDrawer = this.drawer.start(() => {
            this.detailRequest?.abort();
            this.detailRequest = null;
        });
        this.stopObserving = this.host.observe((context) => this.refresh(context));
    }

    stop() {
        this.listRequest?.abort();
        this.detailRequest?.abort();
        this.stopObserving?.();
        this.stopDrawer?.();
        this.host.clearSlots();
        this.drawer.close();
    }

    async refresh(context = this.host.context()) {
        const {projectId, pageId, available} = context;
        if (!projectId || !pageId || pageId === "done" || !available) {
            this.revision++;
            this.listRequest?.abort();
            this.listRequest = null;
            this.host.clearSlots();
            this.drawer.close();
            return;
        }

        const pageKey = `${projectId}:${pageId}`;
        if (this.pageKey !== pageKey) {
            this.pageKey = pageKey;
            this.host.clearSlots();
            this.drawer.close();
        }

        const revision = ++this.revision;
        this.listRequest?.abort();
        this.listRequest = new AbortController();
        try {
            const payload = await this.api.list(
                projectId,
                pageId,
                this.listRequest.signal
            );
            if (revision !== this.revision) {
                return;
            }
            this.host.slots(payload).forEach(({element, occurrence}) => {
                this.inlineRenderer.render(
                    element,
                    occurrence,
                    (annotation, trigger) => this.open(projectId, annotation, trigger)
                );
            });
        } catch (error) {
            if (error.name !== "AbortError") {
                this.host.clearSlots();
                console.warn("Could not load TS4NFDI interview annotations.", error);
            }
        }
    }

    async open(projectId, annotation, trigger) {
        this.detailRequest?.abort();
        this.detailRequest = new AbortController();
        this.drawer.loading(annotation, trigger);
        try {
            const detail = await this.api.detail(
                projectId,
                annotation,
                this.detailRequest.signal
            );
            this.drawer.detail(detail);
        } catch (error) {
            if (error.name !== "AbortError") {
                this.drawer.error(
                    error,
                    () => this.open(projectId, annotation, trigger)
                );
            }
        }
    }
}

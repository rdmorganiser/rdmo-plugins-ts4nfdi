export function createConceptCard({baseUrl}) {
    return {
        render(host, descriptor, {detail}) {
            host.rendered = {
                baseUrl,
                component: descriptor.component,
                label: detail.label
            };
            return () => {
                host.cleaned = true;
            };
        }
    };
}

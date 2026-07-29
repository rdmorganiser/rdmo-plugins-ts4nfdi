function resolveAdapter(module, exportName) {
    const exported = module[exportName || "default"];
    if (!exported) {
        throw new Error(`The module does not export '${exportName || "default"}'.`);
    }
    return exported;
}

export async function loadConfiguredPresentationAdapters(
    registry,
    definitions,
    context = {}
) {
    const registered = [];
    for (const definition of definitions || []) {
        try {
            if (!definition?.name || !definition.module_url) {
                throw new Error("The adapter name and module URL are required.");
            }
            const module = await import(definition.module_url);
            const exported = resolveAdapter(module, definition.export);
            const adapter = typeof exported === "function"
                ? exported(Object.freeze({...context}))
                : exported;
            registry.register(definition.name, adapter);
            registered.push(definition.name);
        } catch (error) {
            console.warn(
                `Could not load presentation adapter '${definition?.name || "unknown"}'.`,
                error
            );
        }
    }
    return registered;
}

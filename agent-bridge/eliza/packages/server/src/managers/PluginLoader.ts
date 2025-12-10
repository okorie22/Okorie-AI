import { logger, type Plugin } from '@elizaos/core';

/**
 * Manages plugin loading and dependency resolution
 */
export class PluginLoader {
  /**
   * Check if an object has a valid plugin shape
   */
  isValidPluginShape(obj: any): obj is Plugin {
    if (!obj || typeof obj !== 'object' || !obj.name) {
      return false;
    }
    return !!(
      obj.init ||
      obj.services ||
      obj.providers ||
      obj.actions ||
      obj.evaluators ||
      obj.description
    );
  }

  /**
   * Validate a plugin's structure
   */
  validatePlugin(plugin: any): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    if (!plugin) {
      errors.push('Plugin is null or undefined');
      return { isValid: false, errors };
    }
    
    if (!plugin.name) {
      errors.push('Plugin must have a name');
    }
    
    if (plugin.actions) {
      if (!Array.isArray(plugin.actions)) {
        errors.push('Plugin actions must be an array');
      } else {
        // Check if actions contain non-objects
        const invalidActions = plugin.actions.filter((a: any) => typeof a !== 'object' || !a);
        if (invalidActions.length > 0) {
          errors.push('Plugin actions must be an array of action objects');
        }
      }
    }
    
    if (plugin.services) {
      if (!Array.isArray(plugin.services)) {
        errors.push('Plugin services must be an array');
      } else {
        // Check if services contain non-objects/non-constructors
        const invalidServices = plugin.services.filter((s: any) => 
          typeof s !== 'function' && (typeof s !== 'object' || !s)
        );
        if (invalidServices.length > 0) {
          errors.push('Plugin services must be an array of service classes or objects');
        }
      }
    }
    
    if (plugin.providers && !Array.isArray(plugin.providers)) {
      errors.push('Plugin providers must be an array');
    }
    
    if (plugin.evaluators && !Array.isArray(plugin.evaluators)) {
      errors.push('Plugin evaluators must be an array');
    }
    
    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Load and prepare a plugin for use
   */
  async loadAndPreparePlugin(pluginName: string): Promise<Plugin | null> {
    logger.info(`[PluginLoader] ========================================`);
    logger.info(`[PluginLoader] Attempting to load plugin: ${pluginName}`);
    logger.info(`[PluginLoader] ========================================`);
    
    try {
      // Try to load the plugin module
      let pluginModule: any;
      
      try {
        logger.debug(`[PluginLoader] Step 1: Importing module: ${pluginName}`);
        logger.debug(`[PluginLoader] This will attempt to resolve: ${pluginName}`);
        // Attempt to dynamically import the plugin
        pluginModule = await import(pluginName);
        logger.debug(`[PluginLoader] ✓ Successfully imported module for ${pluginName}`);
        
        if (pluginModule) {
          const exportKeys = Object.keys(pluginModule);
          logger.debug(`[PluginLoader] Module exports found: ${exportKeys.length} exports`);
          logger.debug(`[PluginLoader] Export names: ${exportKeys.join(', ')}`);
        } else {
          logger.warn(`[PluginLoader] Module imported but is null/undefined`);
        }
      } catch (error) {
        const errorDetails = error instanceof Error 
          ? {
              message: error.message,
              stack: error.stack,
              code: (error as any).code,
              cause: (error as any).cause
            }
          : { error: String(error) };
        
        logger.error(`[PluginLoader] ✗ FAILED to import plugin ${pluginName}`);
        logger.error(`[PluginLoader] Error details:`, JSON.stringify(errorDetails, null, 2));
        logger.error(`[PluginLoader] Common causes:`);
        logger.error(`[PluginLoader]   1. Plugin package not installed - run: bun install`);
        logger.error(`[PluginLoader]   2. Plugin not built - run: cd packages/${pluginName.replace('@elizaos/', '')} && bun run build`);
        logger.error(`[PluginLoader]   3. Plugin package.json missing or incorrect exports`);
        logger.error(`[PluginLoader]   4. Module resolution issue - check node_modules`);
        logger.error(`[PluginLoader]   5. Plugin dist/ folder missing or empty`);
        return null;
      }

      if (!pluginModule) {
        logger.error(`[PluginLoader] ✗ Module imported but is null/undefined for ${pluginName}`);
        return null;
      }

      // Try to find the plugin export in various locations
      const expectedFunctionName = `${pluginName
        .replace(/^@elizaos\/plugin-/, '')
        .replace(/^@elizaos\//, '')
        .replace(/-./g, (match) => match[1].toUpperCase())}Plugin`;

      logger.debug(`[PluginLoader] Step 2: Looking for plugin export in ${pluginName}`);
      logger.debug(`[PluginLoader] Expected function name pattern: ${expectedFunctionName}`);
      logger.debug(`[PluginLoader] Available exports: ${Object.keys(pluginModule).join(', ')}`);

      const exportsToCheck = [
        { name: expectedFunctionName, value: pluginModule[expectedFunctionName] },
        { name: 'default', value: pluginModule.default },
        ...Object.entries(pluginModule).map(([key, value]) => ({ name: key, value })),
      ];

      // Remove duplicates
      const uniqueExports = new Map();
      for (const exp of exportsToCheck) {
        if (!uniqueExports.has(exp.name)) {
          uniqueExports.set(exp.name, exp);
        }
      }
      const finalExports = Array.from(uniqueExports.values());

      logger.debug(`[PluginLoader] Step 3: Checking ${finalExports.length} potential exports...`);

      for (const { name, value: potentialPlugin } of finalExports) {
        const pluginType = typeof potentialPlugin;
        logger.debug(`[PluginLoader]   Checking export "${name}" (type: ${pluginType})`);
        
        if (potentialPlugin === null || potentialPlugin === undefined) {
          logger.debug(`[PluginLoader]     → Export "${name}" is null/undefined, skipping`);
          continue;
        }
        
        if (this.isValidPluginShape(potentialPlugin)) {
          logger.info(`[PluginLoader] ✓✓✓ FOUND VALID PLUGIN in export "${name}" for ${pluginName} ✓✓✓`);
          logger.info(`[PluginLoader] Plugin details:`);
          logger.info(`[PluginLoader]   - Name: ${potentialPlugin.name}`);
          logger.info(`[PluginLoader]   - Has init: ${!!potentialPlugin.init}`);
          logger.info(`[PluginLoader]   - Has services: ${!!potentialPlugin.services} (${potentialPlugin.services?.length || 0} services)`);
          logger.info(`[PluginLoader]   - Has actions: ${!!potentialPlugin.actions} (${potentialPlugin.actions?.length || 0} actions)`);
          logger.info(`[PluginLoader]   - Has providers: ${!!potentialPlugin.providers} (${potentialPlugin.providers?.length || 0} providers)`);
          logger.info(`[PluginLoader]   - Has evaluators: ${!!potentialPlugin.evaluators} (${potentialPlugin.evaluators?.length || 0} evaluators)`);
          logger.info(`[PluginLoader]   - Description: ${potentialPlugin.description || 'N/A'}`);
          return potentialPlugin as Plugin;
        }
        
        // Try factory functions that return a Plugin
        if (typeof potentialPlugin === 'function' && potentialPlugin.length === 0) {
          logger.debug(`[PluginLoader]     → Export "${name}" is a function with 0 args, trying as factory...`);
          try {
            const produced = potentialPlugin();
            if (this.isValidPluginShape(produced)) {
              logger.info(`[PluginLoader] ✓✓✓ FOUND VALID PLUGIN from factory "${name}" for ${pluginName} ✓✓✓`);
              logger.info(`[PluginLoader] Factory-produced plugin name: ${produced.name}`);
              return produced as Plugin;
            } else {
              logger.debug(`[PluginLoader]     → Factory "${name}" did not produce valid plugin shape`);
              logger.debug(`[PluginLoader]     → Produced object has name: ${!!produced?.name}, has required fields: ${!!(produced?.init || produced?.services || produced?.actions)}`);
            }
          } catch (err) {
            const errMsg = err instanceof Error ? err.message : String(err);
            logger.debug(`[PluginLoader]     → Factory export "${name}" threw error: ${errMsg}`);
          }
        } else {
          const hasName = !!potentialPlugin?.name;
          const hasInit = !!potentialPlugin?.init;
          const hasServices = !!potentialPlugin?.services;
          const hasActions = !!potentialPlugin?.actions;
          const hasProviders = !!potentialPlugin?.providers;
          const hasEvaluators = !!potentialPlugin?.evaluators;
          const hasDescription = !!potentialPlugin?.description;
          
          logger.debug(`[PluginLoader]     → Export "${name}" validation:`);
          logger.debug(`[PluginLoader]       - Has name: ${hasName}${hasName ? ` (${potentialPlugin.name})` : ''}`);
          logger.debug(`[PluginLoader]       - Has init: ${hasInit}`);
          logger.debug(`[PluginLoader]       - Has services: ${hasServices}`);
          logger.debug(`[PluginLoader]       - Has actions: ${hasActions}`);
          logger.debug(`[PluginLoader]       - Has providers: ${hasProviders}`);
          logger.debug(`[PluginLoader]       - Has evaluators: ${hasEvaluators}`);
          logger.debug(`[PluginLoader]       - Has description: ${hasDescription}`);
          logger.debug(`[PluginLoader]     → NOT a valid plugin (needs name + at least one of: init/services/providers/actions/evaluators/description)`);
        }
      }

      logger.error(`[PluginLoader] ✗✗✗ COULD NOT FIND VALID PLUGIN EXPORT in ${pluginName} ✗✗✗`);
      logger.error(`[PluginLoader] Checked ${finalExports.length} exports: ${finalExports.map(e => e.name).join(', ')}`);
      logger.error(`[PluginLoader] Plugin must export an object with:`);
      logger.error(`[PluginLoader]   - name: string (required)`);
      logger.error(`[PluginLoader]   - At least one of: init, services, providers, actions, evaluators, description`);
      logger.error(`[PluginLoader] Common fixes:`);
      logger.error(`[PluginLoader]   1. Check plugin's index.ts exports the plugin correctly`);
      logger.error(`[PluginLoader]   2. Ensure plugin has default export or named export matching pattern`);
      logger.error(`[PluginLoader]   3. Verify plugin is built (dist/index.js exists)`);
      return null;
    } catch (error) {
      const errorDetails = error instanceof Error 
        ? {
            message: error.message,
            stack: error.stack,
            name: error.name
          }
        : { error: String(error) };
      logger.error(`[PluginLoader] ✗✗✗ UNEXPECTED ERROR loading plugin ${pluginName} ✗✗✗`);
      logger.error(`[PluginLoader] Error:`, JSON.stringify(errorDetails, null, 2));
      return null;
    }
  }

  /**
   * Resolve plugin dependencies with circular dependency detection
   *
   * Performs topological sorting of plugins to ensure dependencies are loaded in the correct order.
   */
  resolvePluginDependencies(
    availablePlugins: Map<string, Plugin>,
    isTestMode: boolean = false
  ): Plugin[] {
    const resolutionOrder: string[] = [];
    const visited = new Set<string>();
    const visiting = new Set<string>();

    function visit(pluginName: string) {
      if (!availablePlugins.has(pluginName)) {
        logger.warn(`Plugin dependency "${pluginName}" not found and will be skipped.`);
        return;
      }
      if (visited.has(pluginName)) return;
      if (visiting.has(pluginName)) {
        logger.error(`Circular dependency detected involving plugin: ${pluginName}`);
        return;
      }

      visiting.add(pluginName);
      const plugin = availablePlugins.get(pluginName);
      if (plugin) {
        const deps = [...(plugin.dependencies || [])];
        if (isTestMode) {
          deps.push(...(plugin.testDependencies || []));
        }
        for (const dep of deps) {
          visit(dep);
        }
      }
      visiting.delete(pluginName);
      visited.add(pluginName);
      resolutionOrder.push(pluginName);
    }

    for (const name of availablePlugins.keys()) {
      if (!visited.has(name)) {
        visit(name);
      }
    }

    const finalPlugins = resolutionOrder
      .map((name) => availablePlugins.get(name))
      .filter((p) => p) as Plugin[];

    logger.info({ plugins: finalPlugins.map((p) => p.name) }, `Final plugins being loaded:`);

    return finalPlugins;
  }

}
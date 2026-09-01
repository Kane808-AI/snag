const fs = require('fs');
const path = require('path');
const { withDangerousMod, createRunOncePlugin } = require('@expo/config-plugins');

/**
 * expo-sharing currently fixes the extension target name to
 * "expo-sharing-extension". That is fine for Xcode, but it would expose that
 * implementation name in iOS's Share Sheet. Keep the target as-is and give
 * the user-facing extension a product name instead.
 */
function withSnagShareExtensionName(config) {
  return withDangerousMod(config, [
    'ios',
    async (updatedConfig) => {
      const infoPlistPath = path.join(
        updatedConfig.modRequest.platformProjectRoot,
        'expo-sharing-extension',
        'Info.plist'
      );
      const source = fs.readFileSync(infoPlistPath, 'utf8');
      const updated = source.replace(
        /(<key>CFBundleDisplayName<\/key>\s*<string>)\$\(PRODUCT_NAME\)(<\/string>)/,
        '$1Snag$2'
      );

      if (updated === source) {
        throw new Error('Snag Share Sheet name: expected extension display name was not found.');
      }

      fs.writeFileSync(infoPlistPath, updated);
      return updatedConfig;
    },
  ]);
}

module.exports = createRunOncePlugin(
  withSnagShareExtensionName,
  'with-snag-share-extension-name',
  '1.0.0'
);

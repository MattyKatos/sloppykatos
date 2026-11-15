# sloppykatos

Custom Dalamud plugin repository for MattyKatos's plugins.

Paste this URL into Dalamud under **Custom Plugin Repositories**:

https://raw.githubusercontent.com/MattyKatos/sloppykatos/main/repo.json

1. In game, run `/xlsettings`.
2. Open **Experimental**.
3. Add the URL above.
4. Run `/xlplugins` and install the plugin you want.

`repo.json` is a JSON array of Dalamud plugin manifests. XIV Job Gamba is the first entry. Its download links point at the `latest.zip` asset on [xivjobgamba](https://github.com/MattyKatos/xivjobgamba) GitHub Releases. The first package those links expect is the `v1.0.0` release. After that tag's workflow finishes, Dalamud can install it. Later releases are picked up by the sync workflow below.

## Adding a plugin

1. Publish a GitHub Release on the plugin repository. The asset must be a DalamudPackager zip (it contains the plugin DLL and its manifest json). Name the asset `latest.zip`, or choose another name and record it in the list below.
2. Add an object to [`.github/plugins.json`](.github/plugins.json):

```json
{
  "repository": "MattyKatos/your-plugin",
  "asset": "latest.zip"
}
```

3. Run **Sync plugin repository** from the Actions tab, or wait for the schedule (every six hours).

The sync reads the public GitHub API, downloads that asset, and copies the manifest into `repo.json`. An existing `InternalName` is updated in place, so XIV Job Gamba stays first. A new internal name is appended. `AssemblyVersion`, `LastUpdate`, and the three download links (`DownloadLinkInstall`, `DownloadLinkTesting`, `DownloadLinkUpdate`) come from that release. `LastUpdate` is the release's publish time in Unix seconds.

The workflow commits the catalog to `main` as MattyKatos. It uses the built-in `GITHUB_TOKEN` to read public releases and to push this repository. A personal access token is not required while every plugin repository is public.

A private plugin repository would need a personal access token with read access to that repository's releases, stored as an Actions secret and sent with the API request. This workflow does not set that up.

If branch protection blocks the Actions token from pushing to `main`, allow GitHub Actions to bypass the protection. That still does not require a personal access token.

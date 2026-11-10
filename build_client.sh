#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p client/build
# 版本号只写在 version.py；编译进可执行文件，这样正在运行的旧进程不会因磁盘上的应用被替换而报出新版本号。
python3 -B -c 'import version; print("// 由 build_client.sh 根据 version.py 生成，请勿手改。\nlet kongFlowVersion = \"%s\"" % version.VERSION)' > client/build/Version.swift
xcrun swiftc -O -swift-version 5 -enable-bare-slash-regex -module-cache-path /tmp/kongime-swift-cache -module-name Squirrel -target arm64-apple-macos13.0 -import-objc-header client/sources/Squirrel-Bridging-Header.h -I client/librime/src -I client/librime/include -L branding/payload/Squirrel.app/Contents/Frameworks -l rime.1 -Xlinker -rpath -Xlinker @executable_path/../Frameworks client/sources/*.swift client/build/Version.swift -o client/build/Squirrel
xcrun swiftc -module-cache-path /tmp/kongime-swift-cache -O -target arm64-apple-macos13.0 Launcher.swift client/sources/CandidatePhraseLink.swift -o client/build/KongIMESettings

xcrun swiftc -module-cache-path /tmp/kongime-swift-cache -O -target arm64-apple-macos13.0 CredentialStore.swift -o client/build/credential-store
xcrun swiftc -module-cache-path /tmp/kongime-swift-cache -O -target arm64-apple-macos13.0 ChooseFolder.swift -o client/build/choose-folder

xcrun clang++ -std=c++17 -O2 -I client/librime/src LearningTool.cpp -o client/build/learning-tool

xcrun swiftc -module-cache-path /tmp/kongime-swift-cache -O -target arm64-apple-macos13.0 IMEStatus.swift -o client/build/ime-status

xcrun clang++ -std=c++17 -O2 -I client/librime/src EngineCheck.cpp -o client/build/engine-check

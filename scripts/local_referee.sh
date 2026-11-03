#!/usr/bin/env bash
# Optional: run TryAngle Catch referee locally (viewer on http://localhost:8888)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REF="$ROOT/referee"
BOT="${1:-$ROOT/bot.py}"

if [[ ! -d "$REF/.git" ]]; then
  echo "Cloning TryAngle-Catch into referee/ ..."
  git clone --depth 1 https://github.com/eulerscheZahl/TryAngle-Catch.git "$REF"
fi

if ! command -v mvn >/dev/null 2>&1; then
  echo "Maven (mvn) required for local referee." >&2
  exit 1
fi

echo "Building referee (first run downloads deps)..."
(cd "$REF" && mvn -q package -DskipTests)

MAIN="$REF/src/test/java/SkeletonMain.java"
RUNNER_CP="$REF/target/classes"
for j in "$REF"/target/dependency/*.jar; do
  [[ -f "$j" ]] && RUNNER_CP="$RUNNER_CP:$j"
done
# Copy dependencies if missing
if [[ ! -d "$REF/target/dependency" ]]; then
  (cd "$REF" && mvn -q dependency:copy-dependencies -DoutputDirectory=target/dependency)
  for j in "$REF"/target/dependency/*.jar; do
    RUNNER_CP="$RUNNER_CP:$j"
  done
fi

BOT_ABS="$(cd "$(dirname "$BOT")" && pwd)/$(basename "$BOT")"
TMP=$(mktemp -d)
cat > "$TMP/LocalMain.java" <<EOF
import com.codingame.gameengine.runner.MultiplayerGameRunner;

public class LocalMain {
    public static void main(String[] args) {
        MultiplayerGameRunner gameRunner = new MultiplayerGameRunner();
        gameRunner.setLeagueLevel(3);
        gameRunner.addAgent("python3 $BOT_ABS", "local_bot", "");
        gameRunner.addAgent("python3 $BOT_ABS", "mirror_bot", "");
        gameRunner.start();
    }
}
EOF

echo "Compiling local runner entry..."
javac -cp "$RUNNER_CP" -d "$TMP/out" "$TMP/LocalMain.java"

echo "Starting game — open http://localhost:8888 for replay"
java -cp "$TMP/out:$RUNNER_CP" LocalMain

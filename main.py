import subprocess
import time
import statistics
import os
import copy
import shlex
import sys # To check for docker command availability

# --- 設定 ---
# ! ご自身の環境やテストしたいバージョンに合わせて変更してください
LOGSTASH_DOCKER_IMAGE = "docker.elastic.co/logstash/logstash:8.17.4"

NUM_RUNS = 10  # 各オプションでの実行回数

# Logstashに渡す最小限のパイプライン設定 (-e オプション用)
# stdinから入力を受け取り、stdoutに何も出力しない(codec => null)
LOGSTASH_PIPELINE_CONFIG = 'input { stdin {} } filter {} output { stdout {} }'

# テストするJVMオプションのリスト (最初のNoneはオプションなしのベースライン)
JVM_OPTIONS_SETS = [
    (None, "1. ベースライン"),
    ("-Djruby.compile.invokedynamic=false -Djruby.compile.mode=OFF -XX:+TieredCompilation -XX:TieredStopAtLevel=1", "2. オプションあり"),
]

# --- 関数定義 ---

def check_docker():
    """Dockerコマンドが利用可能か確認する"""
    try:
        subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        print("エラー: 'docker' コマンドが見つかりません。Dockerがインストールされ、PATHが通っているか確認してください。", file=sys.stderr)
        return False
    except subprocess.CalledProcessError:
        print("エラー: Dockerデーモンに接続できません。Dockerが起動しているか、実行権限があるか確認してください。", file=sys.stderr)
        print("ヒント: 現在のユーザーを 'docker' グループに追加するか、スクリプトを 'sudo' で実行する必要があるかもしれません。", file=sys.stderr)
        return False

def measure_startup_time(description: str, jvm_opts: str | None):
    """指定されたJVMオプションでDocker上のLogstashを起動し、時間を計測して統計を表示する"""
    durations = []
    print("-" * 50)
    print(f"測定中: {description}")
    print(f"Dockerイメージ: {LOGSTASH_DOCKER_IMAGE}")
    print(f"JVM オプション: {jvm_opts if jvm_opts else 'なし'}")
    print("-" * 50)

    # Dockerコマンドの基本部分
    # --rm: コンテナ終了時に自動削除
    # -i: 標準入力をコンテナに接続 (パイプのため)
    base_command = ['docker', 'run', '--rm', '-i']

    # JVMオプションを環境変数として追加
    if jvm_opts:
        base_command.extend(['-e', f'LS_JAVA_OPTS={jvm_opts}'])

    # イメージ名とLogstashコマンドライン引数を追加
    base_command.append(LOGSTASH_DOCKER_IMAGE)
    base_command.extend(['-e', LOGSTASH_PIPELINE_CONFIG])

    for i in range(1, NUM_RUNS + 1):
        print(f"  実行 {i}/{NUM_RUNS}... ", end="", flush=True)

        try:
            # 開始時間
            start_time = time.perf_counter()

            # Docker経由でLogstashコマンド実行
            process = subprocess.run(
                base_command,
                input='hello\n'.encode(), # stdinに 'hello' を送信
                check=True,
                stdout=subprocess.DEVNULL, # Logstashの標準出力を抑制
                stderr=subprocess.DEVNULL, # Logstashのエラー出力を抑制
            )

            # 終了時間
            end_time = time.perf_counter()

            # 実行時間を計算
            duration = end_time - start_time
            durations.append(duration)
            print(f"完了 ({duration:.3f} 秒)")

        except subprocess.CalledProcessError as e:
            print(f"\nエラー: Dockerコンテナの実行に失敗しました (終了コード: {e.returncode})")
            print(f"コマンド: {' '.join(map(shlex.quote, base_command))}") # 実行したコマンドを表示
            # コンテナのエラーログを確認するには、スクリプト内のstderr=subprocess.DEVNULLをコメントアウトすると良い
            return # この設定でのテストを中止
        except Exception as e:
            print(f"\n予期せぬエラーが発生しました: {e}")
            return # この設定でのテストを中止

        # 念のため少し待機
        time.sleep(1)

    if not durations:
        print("有効な実行データがありません。")
        return

    # 統計情報を計算
    min_time = min(durations)
    max_time = max(durations)
    avg_time = statistics.mean(durations)
    std_dev = statistics.stdev(durations) if len(durations) > 1 else 0.0

    print("\n--- 結果 ---")
    print(f"試行回数: {len(durations)}")
    print(f"最小時間: {min_time:.3f} 秒")
    print(f"最大時間: {max_time:.3f} 秒")
    print(f"平均時間: {avg_time:.3f} 秒")
    print(f"標準偏差: {std_dev:.3f}")
    print("-" * 50)
    print("\n次の測定まで5秒待機...")
    time.sleep(5)

# --- メイン処理 ---
if __name__ == "__main__":
    print("Logstash (Docker) 起動時間測定スクリプト")
    print("-----------------------------------------")

    if not check_docker():
        sys.exit(1)

    print(f"使用イメージ: {LOGSTASH_DOCKER_IMAGE}")
    print(f"各オプションでの実行回数: {NUM_RUNS}")
    print("\n警告: Dockerコマンドの実行権限が必要です。")
    print("      (ユーザーが 'docker' グループに所属しているか、")
    print("       スクリプト自体を 'sudo' で実行する必要があるかもしれません)")
    print("      初回実行時はDockerイメージのダウンロードに時間がかかることがあります。")
    print("      全体の完了まで時間がかかる可能性があります。\n")

    # 各JVMオプションセットで測定を実行
    for opts, desc in JVM_OPTIONS_SETS:
        measure_startup_time(desc, opts)

    print("すべての測定が完了しました。")

"""Exercise the image with a writable bind mount owned by the calling user."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default='minioj-java21:local')
    args = parser.parse_args()

    versions = subprocess.run([
        'docker', 'run', '--rm', '--network', 'none', '--entrypoint', '/bin/sh',
        args.image, '-c',
        'gradle --version && java -version && python3 -c '
        '\'import importlib.metadata; print("MiniOJ " + importlib.metadata.version("minioj"))\'',
    ], capture_output=True, text=True, check=True)
    assert 'Gradle 9.1.0' in versions.stdout
    assert 'version "21' in versions.stderr
    # Use the interpreter in MiniOJ's venv for distribution metadata.
    # python3 is resolved through /opt/minioj/bin by the image PATH.
    assert 'MiniOJ 0.3.0' in versions.stdout

    with tempfile.TemporaryDirectory(prefix='minioj-image-') as temporary:
        root = Path(temporary)
        project = root / 'project'
        source = project / 'src/main/java/Main.java'
        source.parent.mkdir(parents=True)
        source.write_text(
            'public class Main { public static void main(String[] args) { '
            'java.util.Scanner sc = new java.util.Scanner(System.in); '
            'System.out.println(sc.nextInt() + sc.nextInt()); } }\n'
        )
        (project / 'settings.gradle').write_text("rootProject.name = 'image-smoke'\n")
        (project / 'build.gradle').write_text('''
plugins { id 'java' }
java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }
tasks.named('jar') {
    archiveFileName = 'solution.jar'
    manifest { attributes 'Main-Class': 'Main' }
}
tasks.withType(JavaCompile).configureEach {
    options.encoding = 'UTF-8'
    options.release = 21
    options.compilerArgs.add('-proc:none')
}
''')
        config = root / 'config'
        exercise = config / 'w1/ex1'
        exercise.mkdir(parents=True)
        (exercise / 'conf.json').write_text(json.dumps({'name': 'Image smoke', 'stages': [
            {'name': 'Build JAR', 'command': 'timeout 90s gradle --offline --no-daemon --max-workers=2 --console=plain -Dorg.gradle.jvmargs=-Xmx256m clean jar'},
            {'name': 'Run JAR', 'command': 'timeout 4s java -Xmx64m -jar build/libs/solution.jar', 'cased': True},
        ]}))
        for i, (input_text, expected) in enumerate([('2 3\n', '5\n'), ('-8 3\n', '-5\n')]):
            (exercise / f'case{i}.in').write_text(input_text)
            (exercise / f'case{i}.out').write_text(expected)
        output = root / 'feedback.md'
        output.touch()
        command = [
            'docker', 'run', '--rm', '--network', 'none', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--memory', '1g', '--cpus', '2',
            '--pids-limit', '256', '--user', f'{os.getuid()}:{os.getgid()}', '--read-only',
            '--tmpfs', '/tmp:rw,exec,nosuid,nodev,size=512m',
            '--ulimit', 'fsize=268435456:268435456',
            '--mount', f'type=bind,src={project},dst=/workspace',
            '--mount', f'type=bind,src={config},dst=/config,readonly',
            '--mount', f'type=bind,src={output},dst=/feedback.md',
            '--workdir', '/workspace', args.image,
            '--config', '/config', '--comment', '@minioj-bot run w1/ex1',
            '--output', '/feedback.md',
        ]

        def judge():
            process = subprocess.run(command, capture_output=True, text=True, timeout=150)
            assert process.returncode == 0, process.stderr
            assert process.stdout == '', process.stdout
            return output.read_text()

        body = judge()
        assert 'BUILD SUCCESSFUL' in body, body
        assert body.count('Passed!') == 2 and 'Failed...' not in body, body
        jar = project / 'build/libs/solution.jar'
        assert jar.is_file() and jar.stat().st_uid == os.getuid()
        assert output.stat().st_uid == os.getuid()
        print('Writable workspace, host UID/GID, offline Gradle, JAR execution, and Markdown file passed.', flush=True)

        source.write_text('public class Main { broken }\n')
        body = judge()
        assert 'BUILD FAILED' in body and 'Failed...' in body and 'Passed!' not in body, body
        assert not jar.exists(), 'A failed build retained the previously successful JAR'
        print('Compilation failure removes the old JAR and produces failing feedback.', flush=True)

        source.write_text('public class Main { public static void main(String[] args) { while(true) {} } }\n')
        body = judge()
        assert 'BUILD SUCCESSFUL' in body and body.count('Status: 124') == 2, body
        assert 'Passed!' not in body
        print('Nonterminating JARs are stopped by the configured timeout.', flush=True)


if __name__ == '__main__':
    main()

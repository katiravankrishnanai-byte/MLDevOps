pipeline {
  agent any

  environment {
    // REQUIRED: set to a real Docker repo (DockerHub or your registry path)
    IMAGE_REPO = 'katiravan/mldevops'   // change to your repo
    NAMESPACE  = 'mldevopskatir'
    APP_NAME   = 'mldevops'
    SERVICE    = 'mldevops'
    PORT       = '8000'
  }

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        bat 'git --version'
        bat 'docker --version'
        bat 'kubectl version --client=true'
        bat 'git rev-parse HEAD'
      }
    }

    stage('Compute Tags') {
      steps {
        script {
          // Short SHA
          env.SHORTSHA = bat(script: '@git rev-parse --short HEAD', returnStdout: true).trim()

          // Tag pointing at HEAD (optional)
          def tagsRaw = bat(script: '@cmd /c "git tag --points-at HEAD 2>NUL"', returnStdout: true).trim()
          def reltag = ''
          if (tagsRaw) {
            def lines = tagsRaw.readLines().collect { it.trim() }.findAll { it }
            if (lines.size() > 0) reltag = lines[0]
          }
          env.RELTAG = reltag

          // Final image tag
          def effectiveTag = (env.RELTAG && env.RELTAG.trim()) ? env.RELTAG.trim() : "git-${env.SHORTSHA}"
          if (!env.IMAGE_REPO || env.IMAGE_REPO.trim() == '') {
            error("IMAGE_REPO is empty. Set environment.IMAGE_REPO to a real repo name.")
          }
          env.IMAGE = "${env.IMAGE_REPO}:${effectiveTag}"

          echo "SHORTSHA=${env.SHORTSHA}"
          echo "RELTAG=${env.RELTAG}"
          echo "IMAGE=${env.IMAGE}"
        }
      }
    }

    stage('Quality Gate (Lint)') {
      steps {
        bat 'python --version'
        bat 'python -m pip install --upgrade pip'
        bat 'pip install ruff'
        bat 'ruff --version'
        bat 'ruff check src tests'
      }
    }

    stage('QA (Unit Tests)') {
      steps {
        bat 'python -m pip install --upgrade pip'
        bat 'pip install -r requirements.txt'
        bat 'pip install pytest'
        bat 'if not exist reports mkdir reports'
        bat 'python -m pytest -q --junitxml=reports\\test-results.xml'
      }
      post {
        always {
          junit 'reports/test-results.xml'
          archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
      }
    }

    stage('Quality Gate (Dependency Audit)') {
      steps {
        bat 'python -m pip install --upgrade pip'
        bat 'pip install -r requirements.txt'
        bat 'pip install pip-audit'
        bat 'pip-audit -r requirements.txt'
      }
    }

    stage('Build Image') {
      steps {
        bat 'docker build -t "%IMAGE%" .'
      }
    }

    stage('Push Image') {
      when {
        expression { return env.IMAGE_REPO?.trim() }
      }
      steps {
        bat 'docker push "%IMAGE%"'
      }
    }

    stage('Deploy to Kubernetes (Rolling Update)') {
      steps {
        // assumes k8s/deployment.yaml + k8s/service.yaml exist
        bat 'kubectl -n %NAMESPACE% apply -f k8s/'
        // update deployment image
        bat 'kubectl -n %NAMESPACE% set image deployment/%APP_NAME% %APP_NAME%=%IMAGE% --record'
      }
    }

    stage('Rollout Gate (Must Succeed)') {
      steps {
        bat 'kubectl -n %NAMESPACE% rollout status deployment/%APP_NAME% --timeout=180s'
      }
    }

    stage('Rollback Evidence (History + Procedure)') {
      steps {
        bat 'kubectl -n %NAMESPACE% rollout history deployment/%APP_NAME%'
        // Evidence command (manual rollback if needed):
        // kubectl -n %NAMESPACE% rollout undo deployment/%APP_NAME% --to-revision=<N>
      }
    }

    stage('Smoke Test (/health + /predict)') {
      steps {
        script {
          // Port-forward service to localhost for smoke test
          bat '''
            @echo off
            setlocal enabledelayedexpansion
            for /f "tokens=2 delims=: " %%A in ('kubectl -n %NAMESPACE% get svc %SERVICE% ^| findstr /R /C:"%SERVICE%"') do set SVC_FOUND=%%A
            if "%SVC_FOUND%"=="" (
              echo Service %SERVICE% not found in %NAMESPACE%
              exit /b 1
            )
            start "" /B cmd /c "kubectl -n %NAMESPACE% port-forward svc/%SERVICE% 18080:%PORT% > NUL 2>&1"
            timeout /t 3 > NUL
          '''
          // health
          bat 'python - <<PY\nimport httpx\nr=httpx.get("http://127.0.0.1:18080/health",timeout=10)\nprint(r.status_code,r.text)\nr.raise_for_status()\nPY'

          // predict (expects your API accepts JSON {"features":[...]} OR similar)
          // Adjust payload to match your /predict schema
          bat 'python - <<PY\nimport httpx, json\npayload={\"features\":[0,0,0,0,0,0,0,0]}\nr=httpx.post(\"http://127.0.0.1:18080/predict\",json=payload,timeout=20)\nprint(r.status_code,r.text)\nr.raise_for_status()\nPY'
        }
      }
      post {
        always {
          // best-effort kill port-forward
          bat 'taskkill /F /IM kubectl.exe /T >NUL 2>&1 || exit /b 0'
        }
      }
    }

    stage('Load Test (k6)') {
      steps {
        // assumes loadtest/k6.js exists and hits /health and /predict
        bat 'kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found=true'
        bat 'kubectl -n %NAMESPACE% create configmap k6-script --from-file=loadtest\\k6.js'
        bat 'kubectl -n %NAMESPACE% delete job k6 --ignore-not-found=true'
        bat 'kubectl -n %NAMESPACE% apply -f loadtest\\k6-job.yaml'
        bat 'kubectl -n %NAMESPACE% wait --for=condition=complete job/k6 --timeout=300s'
        bat 'kubectl -n %NAMESPACE% logs job/k6'
      }
      post {
        always {
          bat 'kubectl -n %NAMESPACE% delete job k6 --ignore-not-found=true'
          bat 'kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found=true'
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
    }
  }
}

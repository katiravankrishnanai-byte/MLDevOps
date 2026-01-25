```groovy
// Jenkinsfile (FINAL) — Windows agent, Docker + DockerHub, Kubernetes deploy with kubeconfig,
// safe fallbacks, no ansiColor option, no empty image tag, deploy validation bypass if cluster blocks OpenAPI.

pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    // ---- CHANGE THESE 3 ONLY ----
    IMAGE_REPO = 'katiravan/mldevops'          // dockerhub repo
    APP_NAME   = 'mldevops'                   // k8s deployment container name + app name
    NAMESPACE  = 'mldevopskatir'              // k8s namespace

    // ---- OPTIONAL: set to your credential IDs if you have them ----
    // DockerHub username+password credential (type: Username with password)
    DOCKER_CREDS_ID = 'dockerhub-creds'
    // Kubeconfig secret file credential (type: Secret file). Upload your ~/.kube/config as the secret file.
    KUBECONFIG_FILE_CRED_ID = 'kubeconfig-mldevops'

    // Artifacts / reports
    REPORT_DIR = 'reports'
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
          def sha = bat(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
          env.SHORTSHA = sha

          // RELTAG optional: allow SemVer tag from git describe; empty is ok.
          def rel = ''
          try {
            rel = bat(returnStdout: true, script: 'git describe --tags --abbrev=0').trim()
          } catch (ignored) {
            rel = ''
          }
          env.RELTAG = rel

          // Always build a non-empty tag
          env.IMAGE = "${env.IMAGE_REPO}:git-${env.SHORTSHA}"

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
        bat "if not exist %REPORT_DIR% mkdir %REPORT_DIR%"
        bat "python -m pytest -q --junitxml=%REPORT_DIR%\\test-results.xml"
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: "${env.REPORT_DIR}/test-results.xml"
          archiveArtifacts allowEmptyArchive: true, artifacts: "${env.REPORT_DIR}/**"
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
        bat "docker build -t \"%IMAGE%\" ."
      }
    }

    stage('Push Image') {
      steps {
        // If you don't have DOCKER_CREDS_ID, remove withCredentials and login manually on the Jenkins node once.
        withCredentials([usernamePassword(credentialsId: "${env.DOCKER_CREDS_ID}", usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          bat 'echo %DOCKER_PASS% | docker login -u %DOCKER_USER% --password-stdin'
          bat "docker push \"%IMAGE%\""
        }
      }
    }

    stage('Deploy to Kubernetes (Rolling Update)') {
      steps {
        script {
          // Use kubeconfig credential if present; otherwise try local kubectl context.
          def haveKubeCred = (env.KUBECONFIG_FILE_CRED_ID?.trim())

          if (haveKubeCred) {
            withCredentials([file(credentialsId: "${env.KUBECONFIG_FILE_CRED_ID}", variable: 'KUBECONFIG')]) {
              // Create namespace first (idempotent). If you already have namespace.yaml, this is fine.
              bat "kubectl apply -f k8s/namespace.yaml --validate=false"
              // Apply manifests; bypass OpenAPI validation to avoid “/login” HTML from proxy clusters.
              bat "kubectl -n %NAMESPACE% apply -f k8s/ --validate=false"
              // Ensure image is updated even if deployment.yaml hardcodes image
              bat "kubectl -n %NAMESPACE% set image deployment/%APP_NAME% %APP_NAME%=%IMAGE% --record"
            }
          } else {
            bat "kubectl apply -f k8s/namespace.yaml --validate=false"
            bat "kubectl -n %NAMESPACE% apply -f k8s/ --validate=false"
            bat "kubectl -n %NAMESPACE% set image deployment/%APP_NAME% %APP_NAME%=%IMAGE% --record"
          }
        }
      }
    }

    stage('Rollout Gate (Must Succeed)') {
      steps {
        bat "kubectl -n %NAMESPACE% rollout status deployment/%APP_NAME% --timeout=180s"
      }
    }

    stage('Rollback Evidence (History + Procedure)') {
      steps {
        bat "kubectl -n %NAMESPACE% rollout history deployment/%APP_NAME%"
        // Example rollback command for documentation (doesn't execute):
        bat "echo Rollback command (if needed): kubectl -n %NAMESPACE% rollout undo deployment/%APP_NAME% --to-revision=1"
      }
    }

    stage('Smoke Test (/health + /predict)') {
      steps {
        // Port-forward in background, test endpoints, then kill port-forward.
        // Works on Windows using start /B and taskkill.
        bat """
        setlocal enabledelayedexpansion
        for /f "tokens=2 delims=:" %%A in ('kubectl -n %NAMESPACE% get svc %APP_NAME% -o jsonpath^="{.spec.ports[0].port}"') do set SVC_PORT=%%A
        if "!SVC_PORT!"=="" set SVC_PORT=80

        start /B kubectl -n %NAMESPACE% port-forward svc/%APP_NAME% 8000:!SVC_PORT!
        timeout /t 3 /nobreak >nul

        python - <<PY
import httpx, json, sys
base="http://127.0.0.1:8000"
r=httpx.get(base+"/health", timeout=10)
print("health:", r.status_code, r.text)

# If your /predict expects a specific schema, update payload accordingly.
payload={"features":[1,2,3,4,5,6,7,8]}
try:
    rp=httpx.post(base+"/predict", json=payload, timeout=20)
    print("predict:", rp.status_code, rp.text)
except Exception as e:
    print("predict call failed:", e)
    sys.exit(1)
PY

        for /f "tokens=2" %%p in ('tasklist ^| findstr /i "kubectl.exe"') do taskkill /PID %%p /F >nul 2>nul
        endlocal
        """
      }
    }

    stage('Load Test (k6)') {
      steps {
        // Requires loadtest/k6.js in repo. Creates configmap and runs job.
        bat """
        if not exist loadtest\\k6.js (
          echo ERROR: loadtest\\k6.js not found
          exit /b 1
        )

        kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found=true
        kubectl -n %NAMESPACE% create configmap k6-script --from-file=loadtest\\k6.js

        kubectl -n %NAMESPACE% apply -f k8s\\k6-job.yaml --validate=false
        kubectl -n %NAMESPACE% wait --for=condition=complete job/k6 --timeout=240s

        kubectl -n %NAMESPACE% logs job/k6
        kubectl -n %NAMESPACE% delete job k6 --ignore-not-found=true
        kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found=true
        """
      }
    }
  }

  post {
    always {
      archiveArtifacts allowEmptyArchive: true, artifacts: "reports/**, **/Dockerfile, **/requirements.txt, k8s/**, loadtest/**"
    }
  }
}
```

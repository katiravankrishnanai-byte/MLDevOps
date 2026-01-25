pipeline {
  agent any

  environment {
    IMAGE_REPO = "katiravan/mldevops"
    APP_NAME   = "mldevops"
    NAMESPACE  = "mldevopskatir"
    HEALTH_URL = "http://mldevops:8000/health"
    PRED_URL   = "http://mldevops:8000/predict"
  }

  options {
    timestamps()
    disableConcurrentBuilds()
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
          env.SHORTSHA = bat(script: '@git rev-parse --short HEAD', returnStdout: true).trim()
          // RELTAG only if this commit is exactly at a tag; otherwise blank
          def rel = bat(script: '@git describe --tags --exact-match 2>NUL || echo.', returnStdout: true).trim()
          env.RELTAG = (rel == "." ? "" : rel)
          echo "SHORTSHA=${env.SHORTSHA}"
          echo "RELTAG=${env.RELTAG}"
        }
      }
    }

    stage('Quality Gate (Lint)') {
      steps {
        bat '''
          python --version
          python -m pip install --upgrade pip
          python -m pip install ruff
          ruff --version
          ruff check src tests
        '''
      }
    }

    stage('QA (Unit Tests)') {
      steps {
        bat '''
          python -m pip install -r requirements.txt
          python -m pip install pytest
          if not exist reports mkdir reports
          python -m pytest -q --junitxml=reports\\test-results.xml
        '''
      }
      post {
        always {
          junit 'reports/test-results.xml'
          archiveArtifacts artifacts: 'reports/**', fingerprint: true
        }
      }
    }

    stage('Quality Gate (Dependency Audit)') {
      steps {
        // Python-only security gate (no external tool install needed)
        bat '''
          python -m pip install pip-audit
          pip-audit -r requirements.txt || exit /b 1
        '''
      }
    }

    stage('Build Image') {
      steps {
        script {
          env.IMAGE_TAG = "git-${env.SHORTSHA}"
          env.IMAGE = "${env.IMAGE_REPO}:${env.IMAGE_TAG}"
        }
        bat 'docker build -t "%IMAGE%" .'
      }
    }

    stage('Push Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'docker-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          bat '''
            echo %DOCKER_PASS% | docker login -u %DOCKER_USER% --password-stdin || exit /b 1
            docker push "%IMAGE%" || exit /b 1
          '''
        }
      }
    }

    stage('Deploy to Kubernetes (Rolling Update)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl apply -f k8s\\namespace.yaml || exit /b 1
            kubectl apply -f k8s\\service.yaml || exit /b 1
            kubectl apply -f k8s\\deployment.yaml || exit /b 1

            kubectl -n %NAMESPACE% set image deployment/%APP_NAME% %APP_NAME%=%IMAGE% || exit /b 1
            kubectl -n %NAMESPACE% annotate deployment/%APP_NAME% kubernetes.io/change-cause="Jenkins build %BUILD_NUMBER% image %IMAGE% commit %SHORTSHA%" --overwrite || exit /b 1
          '''
        }
      }
    }

    stage('Rollout Gate (Must Succeed)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            set KUBECONFIG=%KUBECONFIG_FILE%
            kubectl -n %NAMESPACE% rollout status deployment/%APP_NAME% --timeout=180s || exit /b 1
            kubectl -n %NAMESPACE% get deploy %APP_NAME% -o wide
            kubectl -n %NAMESPACE% get pods -o wide
          '''
        }
      }
    }

    stage('Rollback Evidence (History + Procedure)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            set KUBECONFIG=%KUBECONFIG_FILE%
            kubectl -n %NAMESPACE% rollout history deployment/%APP_NAME%
            echo Rollback command:
            echo kubectl -n %NAMESPACE% rollout undo deployment/%APP_NAME% --to-revision=REV
          '''
        }
      }
    }

    stage('Smoke Test (/health + /predict)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl -n %NAMESPACE% run curl-%BUILD_NUMBER% --rm -i --restart=Never --image=curlimages/curl -- ^
              curl -sS %HEALTH_URL% || exit /b 1

            kubectl -n %NAMESPACE% run curlpred-%BUILD_NUMBER% --rm -i --restart=Never --image=curlimages/curl -- ^
              curl -sS -X POST %PRED_URL% -H "Content-Type: application/json" -d "{\\"features\\":[0.5,0.5,0.5]}" || exit /b 1
          '''
        }
      }
    }

    stage('Load Test (k6)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl -n %NAMESPACE% delete job k6 --ignore-not-found
            kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found

            kubectl -n %NAMESPACE% create configmap k6-script --from-file=k6.js=loadtest\\k6.js || exit /b 1
            kubectl apply -f loadtest\\k6-job.yaml || exit /b 1

            kubectl -n %NAMESPACE% wait --for=condition=complete job/k6 --timeout=300s || exit /b 1
            kubectl -n %NAMESPACE% logs job/k6

            kubectl -n %NAMESPACE% delete job k6 --ignore-not-found
            kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found
          '''
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'reports/**', fingerprint: true, allowEmptyArchive: true
    }
  }
}

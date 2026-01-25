pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    // ---- EDIT THESE ----
    IMAGE_REPO = 'katiravan/mldevops'
    NAMESPACE  = 'mldevopskatir'
    APP_NAME   = 'mldevops'
    SERVICE    = 'mldevops'
    PORT       = '8000'

    // ---- Derived ----
    SHORTSHA = ''
    RELTAG   = ''
    IMAGE    = ''
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm

        // Prevent Git safety issues on some Jenkins/Windows setups
        bat '@git config --global --add safe.directory "%WORKSPACE%" || ver >NUL'

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

          def tagOut = bat(
            script: '@cmd /c "git tag --points-at HEAD 2>NUL || echo."',
            returnStdout: true
          ).trim()

          env.RELTAG = (tagOut == "." || tagOut == "") ? "" : tagOut.readLines()[0].trim()

          def tag = (env.RELTAG?.trim()) ? env.RELTAG.trim() : "git-${env.SHORTSHA}"
          env.IMAGE = "${env.IMAGE_REPO}:${tag}"

          echo "SHORTSHA=${env.SHORTSHA}"
          echo "RELTAG=${env.RELTAG}"
          echo "IMAGE=${env.IMAGE}"
        }
      }
    }

    stage('Quality Gate (Lint)') {
      steps {
        bat '''
          python --version
          python -m pip install --upgrade pip
          pip install ruff
          ruff --version
          ruff check src tests
        '''
      }
    }

    stage('QA (Unit Tests))') {
      steps {
        bat '''
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest
          if not exist reports mkdir reports
          python -m pytest -q --junitxml=reports\\test-results.xml
        '''
      }
      post {
        always {
          junit 'reports/test-results.xml'
          archiveArtifacts artifacts: 'reports/**', fingerprint: true, allowEmptyArchive: true
        }
      }
    }

    stage('Quality Gate (Dependency Audit)') {
      steps {
        bat '''
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pip-audit
          pip-audit -r requirements.txt
        '''
      }
    }

    stage('Build Image') {
      steps {
        bat 'docker build -t "%IMAGE%" .'
      }
    }

    stage('Push Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'docker-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          bat '''
            echo %DOCKER_PASS% | docker login -u %DOCKER_USER% --password-stdin
            docker push "%IMAGE%"
          '''
        }
      }
    }

    stage('Deploy to Kubernetes (Rolling Update)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl apply -f k8s\\namespace.yaml
            kubectl apply -f k8s\\deployment.yaml
            kubectl apply -f k8s\\service.yaml

            kubectl -n %NAMESPACE% set image deployment/%APP_NAME% %APP_NAME%=%IMAGE%

            kubectl -n %NAMESPACE% annotate deployment/%APP_NAME% ^
              kubernetes.io/change-cause="Jenkins build %BUILD_NUMBER% image %IMAGE% commit %SHORTSHA%" ^
              --overwrite
          '''
        }
      }
    }

    stage('Rollout Gate (Must Succeed)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            set KUBECONFIG=%KUBECONFIG_FILE%
            kubectl -n %NAMESPACE% rollout status deployment/%APP_NAME% --timeout=180s
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
              curl -sS http://%SERVICE%:%PORT%/health

            kubectl -n %NAMESPACE% run curlp-%BUILD_NUMBER% --rm -i --restart=Never --image=curlimages/curl -- ^
              curl -sS -X POST http://%SERVICE%:%PORT%/predict ^
              -H "Content-Type: application/json" ^
              -d "{\\"features\\":[0,0,0,0,0,0,0,0]}"
          '''
        }
      }
    }

    stage('Load Test (k6)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            set KUBECONFIG=%KUBECONFIG_FILE%

            if not exist loadtest\\k6.js (echo ERROR: loadtest\\k6.js not found & exit /b 2)
            if not exist loadtest\\k6-job.yaml (echo ERROR: loadtest\\k6-job.yaml not found & exit /b 2)

            kubectl -n %NAMESPACE% delete job k6 --ignore-not-found
            kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found

            kubectl -n %NAMESPACE% create configmap k6-script --from-file=k6.js=loadtest\\k6.js
            kubectl apply -f loadtest\\k6-job.yaml

            kubectl -n %NAMESPACE% wait --for=condition=complete job/k6 --timeout=300s
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
      archiveArtifacts artifacts: 'k8s/**, loadtest/**, Dockerfile, requirements.txt, src/**, tests/**, reports/**', fingerprint: true, allowEmptyArchive: true
    }
  }
}

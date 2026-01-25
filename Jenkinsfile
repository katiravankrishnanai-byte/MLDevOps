pipeline {
  agent any

  parameters {
    booleanParam(name: 'DO_ROLLBACK', defaultValue: false, description: 'Execute rollback to a specific deployment revision')
    string(name: 'ROLLBACK_TO', defaultValue: '', description: 'Deployment revision number (e.g., 2)')
  }

  environment {
    IMAGE_REPO = "katiravan/mldevops"
    NAMESPACE  = "mldevopskatir"
    APP_NAME   = "mldevops"
    SERVICE    = "mldevops"
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
        bat 'git status'
        bat 'git rev-parse HEAD'
      }
    }

    stage('Compute Tags') {
      steps {
        script {
          env.SHORTSHA = bat(returnStdout: true, script: '@echo off\r\ngit rev-parse --short=7 HEAD').trim()
          def s = bat(returnStatus: true, script: '@echo off\r\ngit describe --tags --exact-match 1> .reltag.txt 2>nul')
          env.RELTAG = (s == 0) ? readFile('.reltag.txt').trim() : ''
        }
        bat '@echo on\necho SHORTSHA=%SHORTSHA%\necho RELTAG=%RELTAG%'
      }
    }

    stage('QA (Unit Tests)') {
      steps {
        bat '''
          @echo on
          python --version
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
          archiveArtifacts artifacts: 'reports/test-results.xml', fingerprint: true
        }
      }
    }

    stage('Validate Tags') {
      steps {
        script {
          if (!(env.SHORTSHA ==~ /^[0-9a-f]{7}$/)) {
            error("Invalid SHORTSHA: ${env.SHORTSHA}")
          }
        }
      }
    }

    stage('Build Image') {
      steps {
        bat '''
          @echo on
          docker build -t "%IMAGE_REPO%:git-%SHORTSHA%" .
        '''
      }
    }

    stage('Push Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'registry-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          bat '''
            @echo on
            echo %DOCKER_PASS% | docker login -u %DOCKER_USER% --password-stdin
            docker push %IMAGE_REPO%:git-%SHORTSHA%
          '''
        }
      }
    }

    stage('Deploy to Kubernetes (Rolling Update)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl apply -f k8s\\namespace.yaml
            kubectl apply -f k8s\\deployment.yaml
            kubectl apply -f k8s\\service.yaml

            kubectl -n %NAMESPACE% set image deployment/%APP_NAME% %APP_NAME%=%IMAGE_REPO%:git-%SHORTSHA%

            kubectl -n %NAMESPACE% annotate deployment/%APP_NAME% ^
              kubernetes.io/change-cause="Jenkins build %BUILD_NUMBER% image %IMAGE_REPO%:git-%SHORTSHA% commit %SHORTSHA%" ^
              --overwrite
          '''
        }
      }
    }

    stage('Rollout Gate (Must Succeed)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
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
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl -n %NAMESPACE% rollout history deployment/%APP_NAME%

            echo Rollback command:
            echo kubectl -n %NAMESPACE% rollout undo deployment/%APP_NAME% --to-revision=REV
          '''
        }
      }
    }

    stage('Rollback Execute (Manual Only)') {
      when {
        expression { return params.DO_ROLLBACK && params.ROLLBACK_TO ==~ /^[0-9]+$/ }
      }
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl -n %NAMESPACE% rollout undo deployment/%APP_NAME% --to-revision=%ROLLBACK_TO%
            kubectl -n %NAMESPACE% rollout status deployment/%APP_NAME% --timeout=180s
          '''
        }
      }
    }

    stage('Smoke Test (/health)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl -n %NAMESPACE% run curl-%BUILD_NUMBER% --rm -i --restart=Never --image=curlimages/curl -- ^
              curl -sS http://%SERVICE%:8000/health
          '''
        }
      }
    }

    stage('Load Test (k6)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl -n %NAMESPACE% delete job k6 --ignore-not-found
            kubectl -n %NAMESPACE% delete configmap k6-script --ignore-not-found

            kubectl -n %NAMESPACE% create configmap k6-script --from-file=k6.js=loadtest\\k6.js

            kubectl apply -f loadtest\\k6-job.yaml
            kubectl -n %NAMESPACE% wait --for=condition=complete job/k6 --timeout=300s
            kubectl -n %NAMESPACE% logs job/k6
          '''
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'reports/**,k8s/**/*,loadtest/**/*,Dockerfile,Jenkinsfile,requirements.txt,README.md', fingerprint: true
    }
  }
}

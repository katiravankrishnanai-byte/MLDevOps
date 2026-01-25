pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    APP_NAME      = 'mldevops'
    NAMESPACE     = 'mldevopskatir'
    DOCKER_REPO   = 'katiravan/mldevops'
    K8S_DIR       = 'k8s'
    PY_SRC        = 'src'
    TEST_DIR      = 'tests'
    REPORTS_DIR   = 'reports'
    MODEL_PATH    = 'models/model.joblib'
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
          def shortSha = bat(returnStdout: true, script: 'git rev-parse --short=7 HEAD').trim()
          def relTag   = (env.RELTAG ?: '').trim()
          env.SHORTSHA = shortSha
          env.IMAGE    = "${env.DOCKER_REPO}:${relTag ? relTag : "git-${shortSha}"}"
          echo "SHORTSHA=${env.SHORTSHA}"
          echo "RELTAG=${relTag}"
          echo "IMAGE=${env.IMAGE}"
        }
      }
    }

    stage('Quality Gate (Lint)') {
      steps {
        bat 'python --version'
        bat 'python -m pip install --upgrade pip'
        bat 'pip install ruff'
        bat "ruff --version"
        bat "ruff check ${env.PY_SRC} ${env.TEST_DIR}"
      }
    }

    stage('QA (Unit Tests)') {
      steps {
        bat 'python -m pip install --upgrade pip'
        bat 'pip install -r requirements.txt'
        bat 'pip install pytest'
        bat "if not exist ${env.REPORTS_DIR} mkdir ${env.REPORTS_DIR}"
        bat "python -m pytest -q --junitxml=${env.REPORTS_DIR}\\test-results.xml"
      }
      post {
        always {
          junit "${env.REPORTS_DIR}/test-results.xml"
          archiveArtifacts artifacts: "${env.REPORTS_DIR}/**", fingerprint: true, allowEmptyArchive: true
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
        bat "docker build -t \"${env.IMAGE}\" ."
      }
    }

    stage('Push Image') {
      environment {
        DOCKERHUB_CREDS = credentials('dockerhub-creds') // Username+Password credential
      }
      steps {
        bat """
          docker login -u "%DOCKERHUB_CREDS_USR%" -p "%DOCKERHUB_CREDS_PSW%"
          docker push "${env.IMAGE}"
        """
      }
    }

    stage('Deploy to Kubernetes (Rolling Update)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
          bat """
            set KUBECONFIG=%KUBECONFIG%
            kubectl config current-context
            kubectl get ns 1>NUL 2>NUL || exit /b 1

            rem Apply namespace first (no schema validation fetch)
            kubectl apply --validate=false -f ${env.K8S_DIR}\\namespace.yaml

            rem Ensure deployment uses the pushed image
            kubectl -n ${env.NAMESPACE} set image deployment/${env.APP_NAME} ${env.APP_NAME}="${env.IMAGE}" --record || echo "set image skipped (deployment may not exist yet)"

            rem Apply remaining manifests
            kubectl apply --validate=false -f ${env.K8S_DIR}\\service.yaml
            kubectl apply --validate=false -f ${env.K8S_DIR}\\deployment.yaml
          """
        }
      }
    }

    stage('Rollout Gate (Must Succeed)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
          bat """
            set KUBECONFIG=%KUBECONFIG%
            kubectl -n ${env.NAMESPACE} rollout status deployment/${env.APP_NAME} --timeout=180s
          """
        }
      }
    }

    stage('Smoke Test (/health + /predict)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
          bat """
            set KUBECONFIG=%KUBECONFIG%

            rem Port-forward to avoid NodePort/Ingress dependencies
            start "" /B kubectl -n ${env.NAMESPACE} port-forward svc/${env.APP_NAME} 8000:8000
            ping 127.0.0.1 -n 6 >NUL

            python -c "import httpx; r=httpx.get('http://127.0.0.1:8000/health', timeout=10); print(r.status_code, r.text); r.raise_for_status()"

            rem Replace payload keys to match your model inputs
            python -c "import httpx, json; payload={'features':[0,0,0,0,0,0,0,0]}; r=httpx.post('http://127.0.0.1:8000/predict', json=payload, timeout=20); print(r.status_code, r.text); r.raise_for_status()"
          """
        }
      }
    }

    stage('Load Test (k6)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
          bat """
            set KUBECONFIG=%KUBECONFIG%

            if not exist loadtest\\k6.js (
              echo ERROR: loadtest\\k6.js not found
              exit /b 2
            )

            kubectl -n ${env.NAMESPACE} delete configmap k6-script --ignore-not-found=true
            kubectl -n ${env.NAMESPACE} create configmap k6-script --from-file=k6.js=loadtest\\k6.js

            kubectl -n ${env.NAMESPACE} delete job k6 --ignore-not-found=true
            kubectl -n ${env.NAMESPACE} apply --validate=false -f ${env.K8S_DIR}\\k6-job.yaml

            kubectl -n ${env.NAMESPACE} wait --for=condition=complete job/k6 --timeout=240s
            kubectl -n ${env.NAMESPACE} logs job/k6
          """
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: "${env.REPORTS_DIR}/**", fingerprint: true, allowEmptyArchive: true
    }
  }
}
